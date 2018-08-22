import json, os, uuid, collections, numbers
import requests, arcpy

line_sep = line_sep_feat = txtLyrNm = txtFldNm = txtFldVal = None
pdfPaths = []   #an array that holds paths for multiple pdf that get combined into a single pdf at the very end
vgap = 0.35     #the vertical gap between two horizontal lines or between text elements
bottomMargin = 0.5
y = topMargin = 10.5
maxCharPerLine = 70 #if the lenght of a value of an attribute is longer than this, the value-string will be broken into multiple line to avoid getting chopped

WebMap_as_JSON = arcpy.GetParameterAsText(0)    
    
#location of mxd to show map(page#1)
# Note: if you want you can make it dynamic based you user's choice from the web app.
#       in that can you need to have a separate parameter to let users pass in their choice of template name.
templateMxd = r"C:\GIS\PrintPopups\A4 Landscape.mxd"
#location of mxd to show only popup information (for page#2 onward)
templateMxdNoMap = r"C:\GIS\PrintPopups\Popups.mxd"
#location of a FileGDB where FeatureClasses (for each graphic layer in the webmap_json) gets created
notesGDB = os.path.join(arcpy.env.scratchFolder, "webmap.gdb")

def splitInMultipleLines(vs):
    arrayString = []
    startPos = 0
    indxSpace = vs.find(' ', startPos + maxCharPerLine)
    while (indxSpace != -1):
        arrayString.append(vs[startPos : indxSpace])
        startPos = indxSpace + 1
        indxSpace = vs.find(' ', startPos + maxCharPerLine)
    arrayString.append(vs[startPos : len(vs)]) #getting the remaining portion
    return '\n'.join(arrayString)

def updateLayoutElementWithFeatureAttributes(lyrNm, flds, features, pdfPaths):
    if (len(features) == 0):
        return

    #y gets reset to the last element's Y coordinate
    # unless it is at the end of the page or new page opened, when it is reset to the page's top margin
    global y

    #lyrNm = lyrDef["name"]
    #flds = None
    #if (lyrDef.has_key("fields")):
    #    flds = lyrDef["fields"]
    #creating a dictionary for field name, field alias pair
    fldNmAliasDict = {}
    if (flds != None):
        for fld in flds:
            fldNmAliasDict[fld["name"]] = fld["alias"]

    ##Note: it is assumed that these elements that are existed in
    ##      the mxd are all horizontal-aligned correctly
    ##      the code here is shifting these 'cloned' elements vertically
    
    # if the elements to draw layer name fall within the bottom margin, move 
    # it to the next page
    if ((y - vgap - vgap - txtLyrNm.elementHeight - 0.15) <= bottomMargin):
        export(m, pdfPaths)
        getMap(templateMxdNoMap)
        #reset(templateMxdNoMap)
        #getElements(m)

    ## Adding layer name ##
    #  adding lines on top
    l = line_sep.clone()
    if (y == topMargin):
        l.elementPositionY = topMargin
    else:
        l.elementPositionY = y - vgap
    y = l.elementPositionY
    
    #  adding a text element for the layer name
    t = txtLyrNm.clone()
    t.text = lyrNm
    t.elementPositionY = y - vgap
    y = t.elementPositionY
    
    #  adding another line below
    l = line_sep.clone()
    l.elementPositionY = y - 0.15
    y = l.elementPositionY

    # looping thru each feature and add text elements for each attribute
    for f in features:
        if (not f.has_key("attributes")):
            continue
        
        attrs = f["attributes"]
        #for fn in fldNmAliasDict:
        for fn in attrs:
            newY = addAttributeOnPage(attrs, fn, y, fldNmAliasDict, flds)
            if (newY == -1): #the previous returns -1 when the attribute value is splitted in multiple line and the textelement grows too big to fit on that page
                export(m, pdfPaths)
                getMap(templateMxdNoMap)
                #adding the multi line text element to the new page
                y = addAttributeOnPage(attrs, fn, y, fldNmAliasDict, flds) #y value gets reset by getMap() function
            else:
                y = newY

            #adding the next line would be outside of the page, so exporting the current page and 
            #   opening a new template for next turns and keep doing that until are turns are written out
            if ((y - vgap) <= bottomMargin):
                export(m, pdfPaths)
                getMap(templateMxdNoMap)
                #reset(templateMxdNoMap)
                #getElements(m)
        
        #once done adding all attributes for one feature
        #  add a new line separator
        l = line_sep_feat.clone()
        l.elementPositionY = y - 0.15
        y = l.elementPositionY

# the function takes a map and an array
# it export the map to a pdf and add the pdf's path in the array
def export(map, pdfPaths):
    delElements()
    s = generateUniqueFileName()
    print s
    arcpy.mapping.ExportToPDF(map, s)
    pdfPaths.append(s)

# removing the elements stored in the original mxd 
# that are already cloned
def delElements():
    global line_sep, line_sep_feat, txtLyrNm, txtFldNm, txtFldVal
    if (line_sep != None):
        line_sep.delete()
        line_sep_feat.delete()
        txtLyrNm.delete()
        txtFldNm.delete()
        txtFldVal.delete()


def addAttributeOnPage(attrs, fn, yCoord, fldNmAliasDict, flds):
    if ((attrs[fn] != None) and (len(str(attrs[fn])) > 0)): #Note: (a) if you want to show attributes with null or empty value, you need to modify this line. 
                                                            #      (b)when value is empty i.e. (len(str(attrs[fn])) == 0) you need set the textElement's text value with a space
        txtFldNmCloned = txtFldNm.clone()
        if (flds != None):
            txtFldNmCloned.text = fldNmAliasDict[fn] #use the alias  fldNmAliasDict[fn]
        else:
            txtFldNmCloned.text = fn   #use field name when fields property is missing from the operation layer               
        txtFldNmCloned.elementPositionY = yCoord - vgap
        
        txtFldValCloned = txtFldVal.clone()
        txtFldValCloned.elementPositionY = yCoord - vgap #this needs to be set up front otherwise the element does not get aligned properly with multi-line text
        if ((isinstance(attrs[fn], numbers.Number)) or (len(attrs[fn]) <= maxCharPerLine)):
            txtFldValCloned.text = attrs[fn]
        else:
            txtFldValCloned.text = splitInMultipleLines(attrs[fn])
            #checks whether adding multiple lines to the textElement makes it too tall to fit on this page
            #    if it won't fit, they gets deleted and gets added to the next page
            if ((txtFldValCloned.elementPositionY - vgap) <= bottomMargin):
                txtFldNmCloned.delete()
                txtFldValCloned.delete()
                return -1 #returning value to inform the caller function that textElement overflows, removed and needs to be added to the next page
        
        return txtFldValCloned.elementPositionY  #new textElements got added, returning new y-coordinates
    else:
        return yCoord  #textELements didn't get added, returning the same yCoord


# reset map variable to point to a new map document based on the mxd path passed into it
def getMap(templateMxdForPopups):
    global m
    del m
    m = arcpy.mapping.MapDocument(templateMxdForPopups)
    getElements(m)

# resetting existing variables to point to elements from the new map
def getElements(m):
    global y, line_sep, line_sep_feat, txtLyrNm, txtFldNm, txtFldVal
    del y, line_sep, line_sep_feat, txtLyrNm, txtFldNm, txtFldVal
    y = topMargin
    lines = arcpy.mapping.ListLayoutElements(m,"GRAPHIC_ELEMENT", "line_sep")
    if (lines.count > 0):
        line_sep = lines[0]
    lines = arcpy.mapping.ListLayoutElements(m,"GRAPHIC_ELEMENT", "line_sep_feat")
    if (lines.count > 0):
        line_sep_feat = lines[0]

    txtElms = arcpy.mapping.ListLayoutElements(m, "TEXT_ELEMENT", "layer_name")
    if (txtElms.count > 0):
        txtLyrNm = txtElms[0]
    txtElms = arcpy.mapping.ListLayoutElements(m, "TEXT_ELEMENT", "field_name")
    if (txtElms.count > 0):
        txtFldNm = txtElms[0]
    txtElms = arcpy.mapping.ListLayoutElements(m, "TEXT_ELEMENT", "field_value")
    if (txtElms.count > 0):
        txtFldVal = txtElms[0]

# combining multiple pdf files into a single pdf file with multiple pages
def combinePdfs(pdfs):
    pdf = arcpy.mapping.PDFDocumentOpen(pdfs[0])
    for i in range(1, len(pdfPaths)):
        pdf.appendPages(pdfPaths[i])
        os.remove(pdfPaths[i])

    pdf.saveAndClose()
    del pdf
    return pdfs[0]

# generating a unique name for each output file
def generateUniqueFileName():
    fileName = 'ags_{}.{}'.format(str(uuid.uuid1()), "pdf")
    fullFileName = os.path.join(arcpy.env.scratchFolder, fileName)
    return fullFileName


if (WebMap_as_JSON == ' '):  #special logic - so that the gp result can be published without needing any json to begin with
    arcpy.SetParameterAsText(1, generateUniqueFileName())
    sys.exit(0)

#Convert the webmap to a map document
result = arcpy.mapping.ConvertWebMapToMapDocument(WebMap_as_JSON, templateMxd, notesGDB)
m = result.mapDocument
export(m, pdfPaths)

#parsing json to all operational layers
js = json.loads(WebMap_as_JSON)
olyrs = js["operationalLayers"]

#getting text and line elements from the map document
getMap(templateMxdNoMap)
        #m = arcpy.mapping.MapDocument(templateMxdNoMap)
        #getElements(m)

#looping thru only graphics-operation-layer and its sub layers
# and add attributes for each features on the layout in tabular format by cloning existing text and line elements
for ol in olyrs:
    if (ol.has_key('featureCollection')):
        fcol = ol["featureCollection"]
        if (not fcol.has_key('layers')):
            continue
        
        lyrs = fcol["layers"]
        
        # only looping thru operation layers that:
        #   (a) are of graphics layer type
        for lyr in lyrs:
            lyrDef = lyr["layerDefinition"]
            fs = lyr["featureSet"]
            flds = lyrDef['fields'] if lyrDef.has_key('fields') else None
            updateLayoutElementWithFeatureAttributes(lyrDef['name'], flds, fs["features"], pdfPaths)

    # if it is a feature layer and has selection
    # then make query to retrieve attributes for selected features
    elif (ol.has_key('url') and ol.has_key('selectionObjectIds')):
        oids = ','.join([str(x) for x in ol['selectionObjectIds']])
        #queryUrl = '{0}/query?objectIds={1}&outFields=*&f=json'.format(ol['url'], oids)
        queryUrl = '{0}/query'.format(ol['url'])
        params = {"objectIds": oids, "outFields": "*", "f": "json"}
        arcpy.AddMessage(queryUrl)
        arcpy.AddMessage(oids)
        r = requests.get(queryUrl, params = params)
        if (r.status_code == 200):
            fs = r.json()
            updateLayoutElementWithFeatureAttributes(ol['title'], fs['fields'], fs["features"], pdfPaths)

#exporting the last page
export(m, pdfPaths)

#combing all pdf files into a single file
Output_File = combinePdfs(pdfPaths)
print 'Output map: {}'.format(Output_File)

# Set the output parameter to be the output file of the server job
arcpy.SetParameterAsText(1, Output_File)
del line_sep, line_sep_feat, txtLyrNm, txtFldNm, txtFldVal, pdfPaths
del m, result


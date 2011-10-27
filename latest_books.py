import hashlib, json, logging, LRSignature, os, sys, traceback, urllib, urllib2
appName="latest_books"

def getAppPath():
    """ This will get us the program's directory, even if we are frozen using py2exe
    This is from http://www.py2exe.org/index.cgi/WhereAmI """
    if hasattr(sys, "frozen"):
        return os.path.dirname(unicode(sys.executable, sys.getfilesystemencoding( )))
    return os.path.dirname(unicode(__file__, sys.getfilesystemencoding( )))

try:
    import configobj
    config=configobj.ConfigObj(os.path.join(getAppPath(), appName+".conf"))
    settings=config["settings"]
except (ImportError, KeyError): #either configobj isn't installed, or the conf file doesn't exist
    args=sys.argv
    username=args[1] if len(args)>1 else raw_input("Please enter your Bookshare username:")
    password=args[2] if len(args)>1 else raw_input("Please enter your Bookshare password:")
    limit=int(args[4]) if len(args)>1 else 250 #amount of books to get, max 250 (see API docs)
    passPhrase=args[3] if len(args)>1 else raw_input("Please enter your key passphrase:")
    key=args[5] if len(args)>1 else raw_input("Please enter your Bookshare API key:")
else:
    username=settings["bookshare_username"]
    password=settings["bookshare_password"]
    limit=settings["bookshare_limit"]
    key=settings["bookshare_key"]
    passPhrase=settings["encryption_passphrase"]

username=urllib.quote_plus(username, safe='/') #take care of spaces and special chars
password_ready=urllib.quote(hashlib.md5(password).hexdigest())
password_header={"X-password":password_ready}
logName=os.path.join(getAppPath(), appName+".log")
base_url="https://api.bookshare.org/book"
base_book_url="http://www.bookshare.org"
formatStr="/format/json"
keyStr="?api_key="+key
limitStr="/limit/"+str(limit)
userStr="/for/"+username
schemas=["bookshare", "dublincore"] #each string must match a key in the schemas dict in makeEnvelope(); only the strings in this list will generate envelopes of their type
path=r"c:\prog\bookshare\LearningRegistry" #path for signed file
signedFileName="latest_books.signed.json"
fingerprint="3CFB2D1C02BB2C154D7849CB369EB2CEAC1E9E2F" #change this as well?
keyLocations=["http://dl.dropbox.com/u/17005121/public_key.txt"] #change this, too?
gpgBin="\"C:\\Program Files (x86)\\GNU\\GnuPG\\pub\\gpg.exe\"" #may be "program files" on 32 bit
publishUrl="http://lrtest02.learningregistry.org/publish"
signer=LRSignature.sign.Sign.Sign_0_21(privateKeyID=fingerprint, passphrase=passPhrase, publicKeyLocations=keyLocations, gpgbin=gpgBin)
doc={"documents":[]}

#get date of last job, if log file exists
#this assumes that the date is the first word on the first line, in mm-dd-yyyy - if you change the logging datefmt, change this too!
if os.path.exists(logName):
    f=open(logName)
    fullDate=f.readline().split(", ")[:2]
    rawDate=fullDate[0]
    fullDate=", ".join([v for v in fullDate])
    #rawDate=fullDate.split(" ")[0]
    date=str(rawDate.replace("-", "")[:8]) #turn "mm-dd-yyyy, " into "mmddyyyy"
    f.close()
else: #hard-code a date from which to start
    fullDate="never, or log file does not exist"
    date="10192011"

logging.basicConfig(format='%(asctime)s, %(levelname)s: %(message)s', datefmt='%m-%d-%Y, %I:%M:%S%p', filename=logName, filemode='w', level=logging.INFO)
logging.info("Job started. Last run was "+fullDate)

def makeEnvelope(schema, data):
    #schema is a string matching a key in the schemas dict below; data is the resource_data
    schemas={ #"schema": ("description", "url/dtd", data_transformer_function)
        "bookshare":
            ("Bookshare Book Metadata Response", "http://developer.bookshare.org/docs/read/api_overview/Request_and_Result_Formats", mapper_bookshare),
        "dublincore":
            ("Dublin Core", "http://purl.org/dc/elements/1.1/", mapper_dublinCore)
    }
    schema=schema.lower() #to avoid caps problems, all keys are lowercase, so make this lowercase too
    transformedData=schemas[schema][2](data) #pass data to the schema's mapper function
    #json of envelope to be written, in python form; each book goes into one of these:
    envelope={
        "doc_type": "resource_data", 
        "doc_version": "0.23.0",  #how do we determine this?
        "resource_data_type": "metadata",
        "active": True,
        "TOS": {"submission_TOS": "http://www.learningregistry.org/tos/cc-by-3-0/v0-5/"},
        "identity": {
            "curator": "",
            "owner": "",
            "submitter": "Alex Hall",
            "signer": "Alex Hall",
            "submitter_type": "agent"
        },
        "resource_locator": data["locator"],
        "keys": [],
        "payload_placement": "inline",
        "payload_schema": [schemas[schema][0]],
        "payload_schema_locator": schemas[schema][1],
        "resource_data": transformedData
    }
    signer.sign(envelope)
    return envelope

#mapper functions:

def mapper_bookshare(data):
    #"url" isn't actually part of the api spec - I add it manually later in the script - so don't copy it
    bs_data={}
    for k, v in data.iteritems():
        if k=="locator": continue
        bs_data[k]=v
    return bs_data

def mapper_dublinCore(data):
    #maps Bookshare json data ("data") to DC XML
    formats={
        "daisy":"ANSI/NISO Z39.86-2005",
        "brf":"Braille-Ready Format"
    }
    s="<?xml version=\"1.0\"?>\
    <!DOCTYPE rdf:RDF PUBLIC \"-//DUBLIN CORE//DCMES DTD 2002/07/31//EN\"\
        \"http://dublincore.org/documents/2002/07/31/dcmes-xml/dcmes-xml-dtd.dtd\">\
    <rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\"\
        xmlns:dc =\"http://purl.org/dc/elements/1.1/\">"
    s+="<rdf:Description rdf:about=\""+data["locator"]+"\">"
    s+="<dc:type>Text</dc:type>"
    s+="<dc:identifier>"+data["isbn13"]+"</dc:identifier>"
    s+="<dc:title>"+data["title"]+"</dc:title>"
    for author in data["author"]:    s+="<dc:creator>"+author+"</dc:creator>"
    for category in data["category"]:    s+="<dc:subject>"+category+"</dc:subject>"
    for format in data["downloadFormat"]:
        if format in formats.keys(): s+="<dc:format>"+formats[format.lower()]+"</dc:format>"
    for l in data["language"]:
        l=l.split(" ")
        l1=l[0].upper()[:2]
        l2=l[1]
        s+="<dc:language>"+l1+"-"+l2+"</dc:language>"
    try: synopsis=data["completeSynopsis"]
    except KeyError: synopsis=data["briefSynopsis"]
    s+="<dc:description>"+synopsis+"</dc:description>"
    s+="<dc:publisher>"+data["publisher"]+"</dc:publisher>"
    s+="<dc:date>"+data["copyright"]+"</dc:date>"
    s+="    </rdf:Description>\
    </rdf:RDF>"
    return s

def containsErrors(res, mode="bs", i=0):
    #mode=="bs": check for Bookshare errors; else check for LR errors
    #"i" is for LR only since each result is an element of a list and may be ok or not
    if mode=="bs".lower():
        root=res["bookshare"]
        if "statusCode" in root.keys():
            logging.error("Error retrieving latest booklist: "+root["messages"][0]+" (code "+str(root["statusCode"])+")")
            return True
    else: #LR errors
        result=res["document_results"][i]
        if not result["OK"]:
            logging.error("Error in envelope: "+str(result["error"]))
            return True
    return False #no errors found

def exceptionHandler(type, value, tb):
    #used to override default exceptions so we can log them, even if we don't catch them
    exc=traceback.format_exception(type, value, tb)
    err="Uncaught Exception:\n"
    err+="".join(line for line in exc)
    logging.error(err)

sys.excepthook=exceptionHandler

#get the json of latest books:
date="09012010" #use to force getting long booklist
envelopes=0 #how many envelopes have been created
enveloped=0 #how many books were put into envelopes - each book has multiple envelopes
url=base_url+"/search/since/"+date+formatStr+limitStr+userStr+keyStr
logging.info("retrieving booklist of books since "+rawDate+" from "+url)
req=urllib2.Request(url, headers=password_header)
res=urllib2.urlopen(req).read()
res=json.loads(res) #pythonize json gotten from reading the url response
if containsErrors(res): #no point in continuing, so exit
    sys.exit(0)
root=res["bookshare"]
#for every book in the booklist, request its metadata using its id:
for book in root["book"]["list"]["result"]:
    id=str(book['id'])
    url=base_url+"/id/"+id+formatStr+userStr+keyStr
    logging.info("Retrieving metadata for \""+book["title"]+"\" with url "+url)
    req=urllib2.Request(url, headers=password_header)
    book=json.loads(urllib2.urlopen(req).read())
    if containsErrors(book): continue #the function will log the errors, but we won't let one book stop the whole script, so skip it
    data=book["bookshare"]["book"]["metadata"]
    logging.debug("book data:\n"+str(data))
    #now see if the book is a textbook/educational material, skip it if it is not:
    if "Textbooks" not in data["category"] and "Educational Materials" not in data["category"]:
        logging.info("Skipping book since it is not in the right categories - it is in "+str(data["category"]))
        continue
    logging.info("Making envelopes from this book\'s metadata. Categories: "+str(data["category"]))
    locator=base_book_url+"/browse/book/"+id
    data["locator"]=locator
    for schema in schemas:
        envelope=makeEnvelope(schema, data)
        doc["documents"].append(envelope)
        envelopes+=1 #number of envelopes created
    enveloped+=1 #number of books that have had envelopes made, regardless of how many actual envelopes each book generates
#put "doc" in json, then write it to our output file
doc_json=json.dumps(doc)
#for final, probably don't need to write this file
signedFile=open(os.path.join(path, signedFileName), 'w')
signedFile.write(doc_json)
signedFile.close()

#publish the file if we have anything to publish:
if envelopes>0:
    publishRequest=urllib2.Request(publishUrl, headers={"Content-type": "application/json; charset=utf-8"})
    logging.info("Publishing data to LR node at "+publishUrl)
    res=json.loads(urllib2.urlopen(publishRequest, data=doc_json).read())
    #now check "res" to make sure everything went okay:
    successes=0
    for i, result in enumerate(res["document_results"]):
       if containsErrors(res, i):
            continue
       successes+=1
    logging.info("Job completed, Found "+str(enveloped)+" books to upload, each of which generated "+str(len(schemas))+" envelopes. Uploaded "+str(successes)+" of "+str(envelopes)+" envelopes successfully.")
else:
    logging.info("No envelopes created, nothing to upload. Job completed.")
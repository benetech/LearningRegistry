import json, logging, LRSignature, os, sys, traceback, urllib2

appName="latest_books"
limit=int(sys.argv[1]) if len(sys.argv)>1 else 250 #amount of books to get, max 250 (see API docs)
key="zftyt9h75pwxvcxqng534m3g" #change this to new key for final
formatStr="/format/json"
keyStr="?api_key="+key
limitStr="/limit/"+str(limit)
base_url="https://api.bookshare.org/book"
base_book_url="http://www.bookshare.org"

#get date of last job, if log file exists
#this assumes that the date is the first word on the first line, in mm-dd-yyyy - if you change the logging datefmt, change this too!
if os.path.exists(appName+".log"):
    f=open(appName+".log")
    fullDate=f.readline().split(", ")[:2]
    rawDate=fullDate[0]
    fullDate=", ".join([v for v in fullDate])
    #rawDate=fullDate.split(" ")[0]
    date=str(rawDate.replace("-", "")[:8]) #turn "mm-dd-yyyy, " into "mmddyyyy"
    f.close()
else: #hard-code a date from which to start
    fullDate="never, or log file does not exist"
    date="10192011"

logging.basicConfig(format='%(asctime)s, %(levelname)s: %(message)s', datefmt='%m-%d-%Y, %I:%M:%S%p', filename=appName+".log", filemode='w', level=logging.INFO)
logging.info("Job started. Last run was "+fullDate)

path=r"c:\prog\bookshare\LearningRegistry" #path for signed file
signedFileName="latest_books.signed.json"
fingerprint="3CFB2D1C02BB2C154D7849CB369EB2CEAC1E9E2F" #change this as well?
keyLocations=["http://dl.dropbox.com/u/17005121/public_key.txt"] #change this, too?
gpgBin="\"C:\\Program Files (x86)\\GNU\\GnuPG\\pub\\gpg.exe\"" #may be "program files" on 32 bit
publishUrl="http://lrtest02.learningregistry.org/publish"
passPhrase=sys.argv[2] if len(sys.argv)>1 else raw_input("Please enter your key passphrase:")
signer=LRSignature.sign.Sign.Sign_0_21(privateKeyID=fingerprint, passphrase=passPhrase, publicKeyLocations=keyLocations, gpgbin=gpgBin)

doc={"documents":[]}

def makeEnvelope(schema, data, url):
    #schema is a string matching a key in the schemas dict below; data is the resource_data; url is the resource_locator
    schemas={ #"schema": ("description", "url/dtd")
        "bookshare":
            ("Bookshare API JSON", "http://developer.bookshare.org/docs/read/api_overview/Request_and_Result_Formats"),
        "otherstandard":
            ("Some other standard", "http://www.somedomain.org/xml/dtd/...")
    }
    schema=schema.lower() #to avoid caps problems, all keys are lowercase, so make this lowercase too
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
        "resource_locator": url,
        "keys": [],
        "payload_placement": "inline",
        "payload_schema": [schemas[schema][0]],
        "payload_schema_locator": schemas[schema][1],
        "resource_data": data
    }
    signer.sign(envelope)
    return envelope

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
#date="09012010" #use to force getting long booklist
envelopes=0 #how many envelopes have been created
url=base_url+"/search/since/"+date+formatStr+limitStr+keyStr
#url=base_book_url+"/id/11111111"+formatStr+keyStr #used to force failure, for testing
logging.info("retrieving booklist of books since "+rawDate+" from "+url)
req=urllib2.Request(url)
res=urllib2.urlopen(req).read()
res=json.loads(res) #pythonize json gotten from reading the url response
if containsErrors(res): #no point in continuing, so exit
    sys.exit(0)
root=res["bookshare"]
#for every book in the booklist, request its metadata using its id:
for book in root["book"]["list"]["result"]:
    id=str(book['id'])
    url=base_url+"/id/"+id+formatStr+keyStr
    logging.info("Retrieving metadata for \""+book["title"]+"\" with url "+url)
    req=urllib2.Request(url)
    book=json.loads(urllib2.urlopen(req).read())
    if containsErrors(book): continue #the function will log the errors, but we won't let one book stop the whole script, so skip it
    data=book["bookshare"]["book"]["metadata"]
    logging.debug("book data:\n"+str(data))
    #now see if the book is a textbook/educational material, skip it if it is not:
    if "Textbooks" not in data["category"] and "Educational Materials" not in data["category"]:
        logging.info("Skipping book since it is not in the right categories - it is in "+str(data["category"]))
        continue
    logging.info("Placing book in envelope for uploading. Categories: "+str(data["category"]))
    url=base_book_url+"/browse/book/"+id
    envelope=makeEnvelope("Bookshare", data, url)
    doc["documents"].append(envelope)
    envelopes+=1

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
    logging.info("Job completed, "+str(successes)+" of "+str(envelopes)+" envelopes successfully uploaded.")
else:
    logging.info("No envelopes created, nothing to upload. Job completed.")
import json, logging, LRSignature, os, urllib2
from copy import deepcopy

appName="latest_books"
limit=2 #amount of books to get, increase to 250 for deployment
key="zftyt9h75pwxvcxqng534m3g" #change this to new key for final
formatStr="/format/json"
keyStr="?api_key="+key
limitStr="/limit/"+str(limit)
base_url="https://api.bookshare.org/book"

#get date of last job, if log file exists
#this assumes that the date is the first word on the first line, in mm-dd-yyyy - if you change the logging datefmt, change this too!
if os.path.exists(appName+".log"):
    f=open(appName+".log")
    rawDate=f.readline().split(" ")[0]
    date=rawDate.replace("-", "")[:8]
    date=str(date)
    f.close()
else: #hard-code a date from which to start
    date="10192011"

logging.basicConfig(format='%(asctime)s, %(levelname)s: %(message)s', datefmt='%m-%d-%Y, %I:%M:%S%p', filename=appName+".log", filemode='w', level=logging.INFO)
logging.info("Job started")

path=r"c:\prog\bookshare\LearningRegistry" #path for signed file
signedFileName="latest_books.signed.json"
fingerprint="3CFB2D1C02BB2C154D7849CB369EB2CEAC1E9E2F" #change this as well?
keyLocations=["http://dl.dropbox.com/u/17005121/public_key.txt"] #change this, too?
gpgBin="\"C:\\Program Files (x86)\\GNU\\GnuPG\\pub\\gpg.exe\"" #may be "program files" on 32 bit
publishUrl="http://lrtest02.learningregistry.org/publish"
passPhrase=raw_input("Please enter your key passphrase:")
signer=LRSignature.sign.Sign.Sign_0_21(privateKeyID=fingerprint, passphrase=passPhrase, publicKeyLocations=keyLocations, gpgbin=gpgBin)

doc={"documents":[]}
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
    "resource_locator": None, #changes to be url of the book in the envelope
    "keys": [],
    "payload_placement": "inline",
    "payload_schema": ["Bookshare API JSON (http://developer.bookshare.org)"],
    #"payload_schema_locator": None,
    "resource_data": None
}
signer.sign(envelope)

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

#get the json of latest books:
envelopes=0 #how many envelopes have been created
url=base_url+"/search/since/"+date+formatStr+limitStr+keyStr
#url=base_url+"/id/11111111"+formatStr+keyStr #used to force failure, for testing
logging.info("retrieving booklist from "+url)
req=urllib2.Request(url)
try: res=urllib2.urlopen(req).read()
except urllib2.URLError, e: logging.exception(e)
res=json.loads(res) #pythonize json gotten from reading the url response
containsErrors(res) #see if bookshare gave us an error, log it if it did
root=res["bookshare"]
#for every book in the booklist, request its metadata using its id:
for book in root["book"]["list"]["result"]:
    id=str(book['id'])
    url=base_url+"/id/"+id+formatStr+keyStr
    logging.info("Retrieving metadata for \""+book["title"]+"\" with url "+url)
    req=urllib2.Request(url)
    book=json.loads(urllib2.urlopen(req).read())
    if containsErrors(book): continue
    data=book["bookshare"]["book"]["metadata"]
    logging.debug("\n"+str(data))
    #now see if the book is a textbook/educational material, skip it if it is not:
    if "Textbooks" not in data["category"] and "Educational Materials" not in data["category"]:
        logging.info("Skipping book since it is not in the right categories - it is in "+str(data["category"]))
        continue
    logging.info("Placing book in envelope for uploading. Categories: "+str(data["category"]))
    locator=base_url+"/browse/book/"+id
    envelope["resource_locator"]=locator
    envelope["resource_data"]=data #set book data for the envelope
    doc["documents"].append(deepcopy(envelope)) #dicts are passed by reference, so no deepcopy means they all get the most recent book value!
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
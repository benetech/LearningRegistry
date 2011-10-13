import json, LRSignature, os, urllib2

limit=2 #amount of books to get, increase to 250 for deployment
key="zftyt9h75pwxvcxqng534m3g" #change this to new key for final
formatStr="/format/json"
keyStr="?api_key="+key
limitStr="/limit/"+str(limit)
base_url="https://api.bookshare.org/book"

path=r"c:\prog\bookshare\LearningRegistry" #path for signed file
signedFileName="latest_books.signed.json"
fingerprint="3CFB2D1C02BB2C154D7849CB369EB2CEAC1E9E2F" #change this as well?
keyLocations=["http://dl.dropbox.com/u/17005121/public_key.txt"] #change this, too?
gpgBin="\"C:\\Program Files (x86)\\GNU\\GnuPG\\pub\\gpg.exe\"" #may be "program files" on 32 bit
publishUrl="http://lrtest01.learningregistry.org/publish" #not working, nor does lrtest02
passPhrase=raw_input("Please enter your key passphrase:")
signer=LRSignature.sign.Sign.Sign_0_21(privateKeyID=fingerprint, passphrase=passPhrase, publicKeyLocations=keyLocations, gpgbin=gpgBin)

#json of document to be written, in python form:
doc={
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
 "resource_locator": None,
 "keys": [],
 "payload_placement": "inline",
 "payload_schema": [],
 "payload_schema_locator": None,
 "payload_locator": None,
 "resource_data": None
}

def checkForErrors(res):
 root=res["bookshare"]
 if "statusCode" in root.keys():
  raise Exception("Error retrieving latest booklist: "+root["messages"][0]+" (code "+str(root["statusCode"])+")")

#get the json of latest books:
books=[]
url=base_url+"/latest"+formatStr+limitStr+keyStr
#url=base_url+"/id/11111111"+formatStr+keyStr #used to force failure for testing
req=urllib2.Request(url)
res=json.loads(urllib2.urlopen(req).read()) #pythonize json gotten from reading the url response
checkForErrors(res) #see if bookshare gave us an error, raise if it did (see function)
root=res["bookshare"]
#for every book in the booklist, request its metadata using its id:
for book in root["book"]["list"]["result"]:
 url=base_url+"/id/"+str(book['id'])+formatStr+keyStr
 req=urllib2.Request(url)
 res=json.loads(urllib2.urlopen(req).read())
 try: checkForErrors(res)
 except: continue
 books.append(res)
#books now has metadata for every book, so put it in the doc in the resource_data field
doc["resource_data"]=books

#sign the "doc" dict that will soon be our json file:
doc=signer.sign(doc)
#put "doc" in json, then write it to our output file
doc_json=json.dumps(doc)
#for final, probably don't need to write this file
signedFile=open(os.path.join(path, signedFileName), 'w')
signedFile.write(doc_json)
signedFile.close()

#publish the file:
publishRequest=urllib2.Request(publishUrl, headers={"Content-type": "application/json; charset=utf-8"})
res=urllib2.urlopen(publishRequest, data=doc_json)
print json.loads(res.read())
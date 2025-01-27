from lr.tests import *
from pylons import config
import couchdb
from routes.util import url_for
import logging
import urllib2
from lxml import etree
from random import choice
import json
import uuid
import datetime
import re
from lr.lib.oaipmh import oaipmh
import pprint

json_headers={'content-type': 'application/json'}

namespaces = {
              "oai" : "http://www.openarchives.org/OAI/2.0/",
              "lr" : "http://www.learningregistry.org/OAI/2.0/",
              "oai_dc" : "http://www.openarchives.org/OAI/2.0/oai_dc/",
              "oai_lr" : "http://www.learningregistry.org/OAI/2.0/oai_dc/",
              "dc":"http://purl.org/dc/elements/1.1/",
              "dct":"http://purl.org/dc/terms/",
              "nsdl_dc":"http://ns.nsdl.org/nsdl_dc_v1.02/",
              "ieee":"http://www.ieee.org/xsd/LOMv1p0",
              "xsi":"http://www.w3.org/2001/XMLSchema-instance"
              }

time_format = '%Y-%m-%d %H:%M:%S.%f'
log = logging.getLogger(__name__)



test_data_delete = True
nsdl_data = { "documents" : [] }
dc_data = { "documents" : [] }



class TestOaiPmhController(TestController):

    @classmethod
    def setUpClass(self):

        schema_file = file("lr/public/schemas/OAI/2.0/OAI-PMH-LR.xsd", "r")
        schema_doc = etree.parse(schema_file)
        self.oailrschema = etree.XMLSchema(schema_doc)
        
        global test_data_delete, nsdl_data, dc_data
        self.o = oaipmh()
        self.server = self.o.server
        self.db = self.o.db
        
        view_data = self.db.view('oai-pmh-test-data/docs')
        if (len(view_data) == 0):
            
            if hasattr(self, "attr"):
                app = self.app
            else:
                controller =  TestOaiPmhController(methodName="test_empty")
                app = controller.app
            
            nsdl_data = json.load(file("lr/tests/data/nsdl_dc/data-000000000.json"))
            for doc in nsdl_data["documents"]:
                doc["doc_ID"] = "NSDL-TEST-DATA-"+str(uuid.uuid1())
            
            app.post('/publish', params=json.dumps(nsdl_data), headers=json_headers)
            
            dc_data = json.load(file("lr/tests/data/oai_dc/data-000000000.json"))
            for doc in dc_data["documents"]:
                doc["doc_ID"] = "OAI-DC-TEST-DATA-"+str(uuid.uuid1())
                
            app.post('/publish', params=json.dumps(dc_data), headers=json_headers)
            view_data = self.db.view('oai-pmh/test-data')
        
        nsdl_data = { "documents" : [] }
        dc_data = { "documents" : [] }
        for row in view_data:
            if re.search("^NSDL-TEST-DATA-", row.key) != None and re.search("-distributable$", row.key) == None:
                nsdl_data["documents"].append(row.value)
            if re.search("^OAI-DC-TEST-DATA-", row.key) != None and re.search("-distributable$", row.key) == None:
                dc_data["documents"].append(row.value)
        opts = {
                "startkey":"_design/",
                "endkey": "_design0",
                "include_docs": True
        }
        
        # Force indexing in oai views 
        design_docs = self.db.view('_all_docs', **opts)
        for row in design_docs:
            if re.match("^_design/oai-pmh-", row.key) != None and "views" in row.doc and len(row.doc["views"].keys()) > 0:
                view_name = "{0}/_view/{1}".format( row.key, row.doc["views"].keys()[0])
                log.error("Indexing: {0}".format( view_name))
                self.db.view(view_name, limit=1, descending=True)
            else:
                log.error("Not Indexing: {0}".format( row.key))
        
        
    @classmethod       
    def tearDownClass(self):
        global test_data_delete
        
        if test_data_delete == True:
            for doc in nsdl_data["documents"]:
                del self.db[doc["_id"]]
                try:
                    del self.db["{0}-distributable".format(doc["_id"])]
                except:
                    pass
            for doc in dc_data["documents"]:
                del self.db[doc["_id"]]
                try:
                    del self.db["{0}-distributable".format(doc["_id"])]
                except:
                    pass
        else:
            log.error("Not deleting test data!!!")
                
    def _get_timestamps(self, doc1, doc2):
        if doc1["node_timestamp"] < doc2["node_timestamp"]:
            from_ =  doc1["node_timestamp"]
            until_ = doc2["node_timestamp"]
        else:
            until_ =  doc1["node_timestamp"]
            from_ = doc2["node_timestamp"]
        
        from_ = re.sub("\.[0-9]+Z", "Z", from_)
        until_ = re.sub("\.[0-9]+Z", "Z", until_)
        
        return (from_, until_)
    
    def validate_lr_oai_response(self, response, errorExists=False, checkSchema=False, errorCodeExpected=None):
        if hasattr(response, "lxml"):
            xmlcontent = response.lxml
        else:
            body = response.body
            xmlcontent = etree.fromstring(body)
        
        
        
        error = xmlcontent.xpath("//*[local-name()='error']", namespaces=namespaces)
        if errorExists == False:
            if len(error) > 0:
                self.assertEqual(0, len(error), "validate_lr_oai_response FAIL: Error code:{0} mesg:{1}".format(error[0].xpath("@code", namespaces=namespaces)[0], error[0].xpath("text()", namespaces=namespaces)[0]))
        elif errorExists and errorCodeExpected != None:
            codeReceived = error[0].xpath("@code", namespaces=namespaces)[0]
            if errorCodeExpected != codeReceived:
                self.assertEqual(0, len(error), "validate_lr_oai_response FAIL: Expected:{2}, Got Error code:{0} mesg:{1}".format(error[0].xpath("@code", namespaces=namespaces)[0], error[0].xpath("text()", namespaces=namespaces)[0], errorCodeExpected))
        else:
            self.assertEqual(1, len(error), "validate_lr_oai_response FAIL: Expected error, none found.")
        
        
        if checkSchema == True:
            self.oailrschema.assertValid(xmlcontent)
        else:
            log.info("validate_lr_oai_response: Not validating response against schema.")
        
    def test_empty(self):
            pass
        
    def test_get_oai_lr_schema(self):
        response = urllib2.urlopen("http://www.w3.org/2001/XMLSchema.xsd");
        body = response.read()
        xmlSchema = etree.XMLSchema(etree.fromstring(body))
        
        response = self.app.get("/schemas/OAI/2.0/OAI-PMH-LR.xsd")
        oaiLRSchema = etree.fromstring(response.body)
        
        assert xmlSchema.validate(oaiLRSchema)
        log.info("test_get_oai_lr_schema: pass")
        
        
    def test_identify_get(self):
        response = self.app.get("/OAI-PMH", params={'verb': 'Identify'})
        self.validate_lr_oai_response(response)
        log.info("test_identify_get: pass")
        
    def test_identify_post(self):
        response = self.app.post("/OAI-PMH", params={'verb': 'Identify'})
        self.validate_lr_oai_response(response)
        log.info("test_identify_post: pass")
        
        
    def test_ListSets_get(self):
        response = self.app.get("/OAI-PMH", params={'verb': 'ListSets'})
        self.validate_lr_oai_response(response, errorExists=True, errorCodeExpected="noSetHierarchy")
        log.info("test_ListSets_get: pass")
        
    def test_ListSets_post(self):
        response = self.app.post("/OAI-PMH", params={'verb': 'ListSets'})
        self.validate_lr_oai_response(response, errorExists=True, errorCodeExpected="noSetHierarchy")
        log.info("test_ListSets_post: pass")
        
        
        
    def test_listMetadataFormats_get(self):
        response = self.app.get("/OAI-PMH", params={'verb': 'ListMetadataFormats'})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_listMetadataFormats_get: fail")
            log.exception("test_listMetadataFormats_get: fail")
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_listMetadataFormats_get: pass")
        
    def test_listMetadataFormats_post(self):
        response = self.app.post("/OAI-PMH", params={'verb': 'ListMetadataFormats'})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_listMetadataFormats_post: fail")
            log.exception("test_listMetadataFormats_post: fail")
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_listMetadataFormats_post: pass")
    
    def test_namespaceDeclarations(self):
        # according to the spec, all namespace used in the metadata
        # element should be declared on the metadata element,
        # and not on root or ancestor elements (big sigh..)
        # this works, except for the xsi namespace which is allready declared
        # on the root element, which means lxml will not declare it again on
        # the metadata element
        randomDoc = choice(dc_data["documents"])
        response = self.app.get("/OAI-PMH", params={'verb': 'GetRecord', 'metadataPrefix':'oai_dc', 'identifier': randomDoc["doc_ID"], 'by_doc_ID': True})
        tree = etree.fromstring(response.body)
        
        metadata = tree.xpath("//oai_dc:dc", namespaces=namespaces)
        
        if len(metadata) != 1:
            self.fail("test_namespaceDeclarations: fail - Missing Metadata")
        else:
            for meta in metadata:
                log.info("test_namespaceDeclarations medatdada: prefix:{0} name:{1}".format(meta.prefix, meta.tag))
                pat = "<oai_dc:dc[^>]*\sxmlns:{0}=".format(meta.prefix)
                self.assertTrue(str(re.match(pat, etree.tostring(meta), flags=re.MULTILINE)!=None), "test_namespaceDeclarations: fail - namespace declaration not present")
        


    def test_getRecord_by_doc_ID_get(self):
        global nsdl_data, dc_data
        randomDoc = choice(dc_data["documents"])
        response = self.app.get("/OAI-PMH", params={'verb': 'GetRecord', 'metadataPrefix':'oai_dc', 'identifier': randomDoc["doc_ID"], 'by_doc_ID': True})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_getRecord_by_doc_ID_get: fail - identifier: {0}".format(randomDoc["doc_ID"]))
            log.exception("test_getRecord_by_doc_ID_get: fail - identifier: {0}".format(randomDoc["doc_ID"]))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_getRecord_by_doc_ID_get: pass")
        
    def test_getRecord_by_doc_ID_post(self):
        global nsdl_data, dc_data
        randomDoc = choice(dc_data["documents"])
        response = self.app.post("/OAI-PMH", params={'verb': 'GetRecord', 'metadataPrefix':'oai_dc', 'identifier': randomDoc["doc_ID"], 'by_doc_ID': True})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_getRecord_by_doc_ID_post: fail - identifier: {0}".format(randomDoc["doc_ID"]))
            log.exception("test_getRecord_by_doc_ID_post: fail - identifier: {0}".format(randomDoc["doc_ID"]))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_getRecord_by_doc_ID_post: pass")
        
    def test_getRecord_by_resource_ID_get(self):
        global nsdl_data, dc_data
        randomDoc = choice(dc_data["documents"])
        response = self.app.get("/OAI-PMH", params={'verb': 'GetRecord', 'metadataPrefix':'oai_dc', 'identifier': randomDoc["resource_locator"], 'by_resource_ID': True})
        try:
            self.validate_lr_oai_response(response)
        except AssertionError:
            global test_data_delete
            log.exception("test_getRecord_by_resource_ID_get: fail - identifier: {0}".format(randomDoc["resource_locator"]))
            test_data_delete = False
            raise
        except Exception as e:
#            log.error("test_getRecord_by_resource_ID_get: fail - identifier: {0}".format(randomDoc["resource_locator"]))
            log.exception("test_getRecord_by_resource_ID_get: fail - identifier: {0}".format(randomDoc["resource_locator"]))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_getRecord_by_resource_ID_get: pass")
        
    def test_getRecord_by_resource_ID_post(self):
        global nsdl_data, dc_data
        randomDoc = choice(dc_data["documents"])
        response = self.app.post("/OAI-PMH", params={'verb': 'GetRecord', 'metadataPrefix':'oai_dc', 'identifier': randomDoc["resource_locator"], 'by_resource_ID': True})
        try:
            self.validate_lr_oai_response(response)
        except AssertionError:
            global test_data_delete
            log.exception("test_getRecord_by_resource_ID_post: fail - identifier: {0}".format(randomDoc["resource_locator"]))
            test_data_delete = False
            raise
        except Exception as e:
#            log.error("test_getRecord_by_resource_ID_post: fail - identifier: {0}".format(randomDoc["resource_locator"]))
            log.exception("test_getRecord_by_resource_ID_post: fail - identifier: {0}".format(randomDoc["resource_locator"]))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_getRecord_by_resource_ID_post: pass")


    def test_listRecords_post(self):
        global nsdl_data, dc_data
        doc1 = choice(nsdl_data["documents"])
        doc2 = choice(nsdl_data["documents"])
        
        (from_, until_) = self._get_timestamps(doc1, doc2)
            
        response = self.app.post("/OAI-PMH", params={'verb': 'ListRecords', 'metadataPrefix': 'nsdl_dc', 'from': from_, 'until': until_})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_listRecords_post: fail - from: {0} until: {1}".format(from_, until_))
            log.exception("test_listRecords_post: fail - from: {0} until: {1}".format(from_, until_))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_listRecords_post: pass")
        
    def test_listRecords_get(self):
        global nsdl_data, dc_data
        doc1 = choice(nsdl_data["documents"])
        doc2 = choice(nsdl_data["documents"])
        
        (from_, until_) = self._get_timestamps(doc1, doc2)
            
        response = self.app.get("/OAI-PMH", params={'verb': 'ListRecords', 'metadataPrefix': 'nsdl_dc', 'from': from_, 'until': until_})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_listRecords_get: fail - from: {0} until: {1}".format(from_, until_))
            log.exception("test_listRecords_get: fail - from: {0} until: {1}".format(from_, until_))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_listRecords_get: pass")
        
        
    def test_listIdentifiers_post(self):
        global nsdl_data, dc_data
        doc1 = choice(nsdl_data["documents"])
        doc2 = choice(nsdl_data["documents"])
        
        (from_, until_) = self._get_timestamps(doc1, doc2)
            
        response = self.app.post("/OAI-PMH", params={'verb': 'ListIdentifiers', 'metadataPrefix': 'nsdl_dc', 'from': from_, 'until': until_})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_listIdentifiers_post: fail - from: {0} until: {1}".format(from_, until_))
            log.exception("test_listIdentifiers_post: fail - from: {0} until: {1}".format(from_, until_))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_listIdentifiers_post: pass")
        
    def test_listIdentifiers_get(self):
        global nsdl_data, dc_data
        doc1 = choice(nsdl_data["documents"])
        doc2 = choice(nsdl_data["documents"])
        
        (from_, until_) = self._get_timestamps(doc1, doc2)
            
        response = self.app.get("/OAI-PMH", params={'verb': 'ListIdentifiers', 'metadataPrefix': 'nsdl_dc', 'from': from_, 'until': until_})
        try:
            self.validate_lr_oai_response(response)
        except Exception as e:
#            log.error("test_listIdentifiers_get: fail - from: {0} until: {1}".format(from_, until_))
            log.exception("test_listIdentifiers_get: fail - from: {0} until: {1}".format(from_, until_))
            global test_data_delete
            test_data_delete = False
            raise e
        log.info("test_listIdentifiers_get: pass")


#    def test_index(self):
#        response = self.app.get(url('OAI-PMH'))
#        # Test response...
#
#    def test_GET(self):
#        response = self.app.get(url('formatted_OAI-PMH', format='xml'))
#
#    def test_POST(self):
#        response = self.app.post(url('OAI-PMH'))

###############################

#    def test_getRecord(self):
#        tree = self._server.getRecord(
#            metadataPrefix='oai_dc', identifier='hdl:1765/315')
#        self.assert_(oaischema.validate(tree))
#        
#    def test_identify(self):
#        tree = self._server.identify()
#        self.assert_(oaischema.validate(tree))
#
#    def test_listIdentifiers(self):
#        tree = self._server.listIdentifiers(
#            from_=datetime(2003, 4, 10),
#            metadataPrefix='oai_dc')
#        self.assert_(oaischema.validate(tree))
#        
#    def test_listMetadataFormats(self):
#        tree = self._server.listMetadataFormats()
#        self.assert_(oaischema.validate(tree))
#
#    def test_listRecords(self):
#        tree = self._server.listRecords(
#            from_=datetime(2003, 4, 10),
#            metadataPrefix='oai_dc')
#        self.assert_(oaischema.validate(tree))
#
#    def test_listSets(self):
#        tree = self._server.listSets()
#        self.assert_(oaischema.validate(tree))
#
#    def test_namespaceDeclarations(self):
#        # according to the spec, all namespace used in the metadata
#        # element should be declared on the metadata element,
#        # and not on root or ancestor elements (big sigh..)
#        # this works, except for the xsi namespace which is allready declared
#        # on the root element, which means lxml will not declare it again on
#        # the metadata element
#
#        tree = self._server.getRecord(
#            metadataPrefix='oai_dc', identifier='hdl:1765/315')
#        # ugly xml manipulation, this is probably why the requirement is in
#        # the spec (yuck!)
#        xml = etree.tostring(tree)
#        xml = xml.split('<metadata>')[-1].split('</metadata>')[0]
#        first_el = xml.split('>')[0]
#        self.assertTrue(first_el.startswith('<oai_dc:dc'))
#        self.assertTrue(
#            'xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"'
#            in first_el) 
#        self.assertTrue(
#            'xmlns:dc="http://purl.org/dc/elements/1.1/"'
#            in first_el)

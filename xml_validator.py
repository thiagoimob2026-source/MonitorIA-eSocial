from lxml import etree
import os

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    import sys
    try:
        base_path = sys._MEIPASS
    except Exception:
        # Em modo dev, usamos o diretorio do arquivo fonte
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class XMLValidator:
    def __init__(self, schema_dir="schemas"):
        self.schema_dir = get_resource_path(schema_dir)

    def validate_s1200(self, xml_str):
        return self._validate(xml_str, "evtRemun.xsd")

    def validate_s1202(self, xml_str):
        return self._validate(xml_str, "evtRmnRPPS.xsd")

    def validate_s1207(self, xml_str):
        return self._validate(xml_str, "evtBenPrRP.xsd")

    def validate_s1210(self, xml_str):
        return self._validate(xml_str, "evtPgtos.xsd")

    def validate_s3000(self, xml_str):
        return self._validate(xml_str, "evtExclusao.xsd")

    def validate(self, xml_str, evt_type):
        """Auto-select validator by event type string (e.g. 'S-1200')."""
        mapping = {
            "S-1200": "evtRemun.xsd",
            "S-1202": "evtRmnRPPS.xsd",
            "S-1207": "evtBenPrRP.xsd",
            "S-1210": "evtPgtos.xsd",
            "S-3000": "evtExclusao.xsd",
        }
        xsd = mapping.get(evt_type)
        if not xsd:
            return None, [f"Sem schema XSD local para {evt_type}"]
        return self._validate(xml_str, xsd)

    def _validate(self, xml_str, xsd_file):
        xsd_path = os.path.join(self.schema_dir, xsd_file)
        if not os.path.exists(xsd_path):
            return False, [f"Arquivo XSD não encontrado: {xsd_path}"]

        try:
            # parser and parse() are better for resolving includes relative to the file's dir
            parser = etree.XMLParser(remove_blank_text=True)
            schema_doc = etree.parse(xsd_path, parser)
            schema = etree.XMLSchema(schema_doc)
            
            # Parse XML
            xml_doc = etree.fromstring(xml_str.encode('utf-8'))
            
            # Injection of dummy Signature if missing (XSD requires it)
            if xml_doc.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is None:
                self._inject_dummy_signature(xml_doc)
            
            # Validate
            schema.assertValid(xml_doc)
            return True, []
        except etree.DocumentInvalid as e:
            # Format error messages for humans
            errors = []
            for error in e.error_log:
                # Clean up technical messages
                msg = error.message
                if "{" in msg: # Remove namespaces from message for clarity
                    import re
                    msg = re.sub(r'\{.*?\}', '', msg)
                errors.append(f"Linha {error.line}: {msg}")
            return False, errors
        except Exception as e:
            return False, [f"Erro interno no validador: {e}"]

    def _inject_dummy_signature(self, xml_doc):
        """Adds a placeholder signature to satisfy XSD requirements during pre-validation."""
        ds_ns = "http://www.w3.org/2000/09/xmldsig#"
        sig = etree.Element("{%s}Signature" % ds_ns, nsmap={'ds': ds_ns})
        sinfo = etree.SubElement(sig, "{%s}SignedInfo" % ds_ns)
        etree.SubElement(sinfo, "{%s}CanonicalizationMethod" % ds_ns, Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        etree.SubElement(sinfo, "{%s}SignatureMethod" % ds_ns, Algorithm="http://www.w3.org/2001/04/xmldsig-more#rsa-sha256")
        ref = etree.SubElement(sinfo, "{%s}Reference" % ds_ns, URI="")
        trans = etree.SubElement(ref, "{%s}Transforms" % ds_ns)
        etree.SubElement(trans, "{%s}Transform" % ds_ns, Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature")
        etree.SubElement(trans, "{%s}Transform" % ds_ns, Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
        # Use valid base64 strings to satisfy XSD types (binary)
        dummy_b64 = "MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTI="
        
        etree.SubElement(ref, "{%s}DigestMethod" % ds_ns, Algorithm="http://www.w3.org/2001/04/xmlenc#sha256")
        etree.SubElement(ref, "{%s}DigestValue" % ds_ns).text = dummy_b64
        etree.SubElement(sig, "{%s}SignatureValue" % ds_ns).text = dummy_b64
        key_info = etree.SubElement(sig, "{%s}KeyInfo" % ds_ns)
        x509_data = etree.SubElement(key_info, "{%s}X509Data" % ds_ns)
        etree.SubElement(x509_data, "{%s}X509Certificate" % ds_ns).text = dummy_b64
        
        # In eSocial events (S-1.3), the Signature is a sibling of the event node (e.g. evtRemun)
        # both are children of the <eSocial> root.
        xml_doc.append(sig)

if __name__ == "__main__":
    # Test stub
    v = XMLValidator()
    print("Validador pronto.")

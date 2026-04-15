import os
import subprocess
import tempfile
import uuid
from lxml import etree
import json
import time

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    import sys
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Em modo dev, usamos o diretorio do arquivo fonte
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class ESocialNativeSender:
    def __init__(self, console_log_callback=print):
        self.log = console_log_callback
        self.client_path = get_resource_path("native/esocial_client.exe")
        self.url_homolog = "https://webservices.producaorestrita.esocial.gov.br/servicos/empregador/enviarloteeventos/WsEnviarLoteEventos.svc"
        self.url_prod = "https://webservices.envio.esocial.gov.br/servicos/empregador/enviarloteeventos/WsEnviarLoteEventos.svc"
        self.url_consult_homolog = "https://webservices.producaorestrita.esocial.gov.br/servicos/empregador/consultarloteeventos/WsConsultarLoteEventos.svc"
        self.url_consult_prod = "https://webservices.consulta.esocial.gov.br/servicos/empregador/consultarloteeventos/WsConsultarLoteEventos.svc"

    def consult_lote(self, protocol, nr_insc, tp_amb="2"):
        """
        Consults the processing status of a batch using its protocol.
        """
        # Official namespace from the project's WSDL (WsConsultarLoteEventos-v1_1_0.wsdl)
        ns_envio = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/consulta/retornoProcessamento/v1_1_0"
        ns_conclote = "http://www.esocial.gov.br/schema/lote/eventos/envio/consulta/retornoProcessamento/v1_0_0"
        
        root = etree.Element("{%s}ConsultarLoteEventos" % ns_envio, nsmap={None: ns_envio})
        consulta = etree.SubElement(root, "{%s}consulta" % ns_envio)
        
        esocial = etree.SubElement(consulta, "eSocial", nsmap={None: ns_conclote})
        consult_node = etree.SubElement(esocial, "consultaLoteEventos")
        
        etree.SubElement(consult_node, "protocoloEnvio").text = str(protocol)
        
        batch_content = etree.tostring(root, encoding="utf-8", xml_declaration=False).decode('utf-8')
        
        url = self.url_consult_prod if tp_amb == "1" else self.url_consult_homolog
        
        # Exact SOAPAction from WSDL
        soap_action = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/consulta/retornoProcessamento/v1_1_0/ServicoConsultarLoteEventos/ConsultarLoteEventos"
        
        self.log(f"Consultando Protocolo: {protocol}...")
        return self.transmit_native(batch_content, url, nr_insc, soap_action)

    def send_lote(self, xml_events, nr_insc, tp_amb="2"):
        """
        Receives a list of SIGNED individual event XML strings and sends as a batch.
        """
        batch_xml = self.wrap_in_batch(xml_events, nr_insc)
        
        url = self.url_prod if tp_amb == "1" else self.url_homolog
        
        # We use a native C# transmitter because it handles A3 token mTLS handshake 
        # much better than PowerShell or Python directly.
        return self.transmit_native(batch_xml, url, nr_insc)

    def wrap_in_batch(self, signed_event_xmls, nr_insc):
        ns_envio = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0"
        ns_lote = "http://www.esocial.gov.br/schema/lote/eventos/envio/v1_1_1"
        
        # Note: namespaces must match precisely S-1.3 requirements for Batch
        root = etree.Element("{%s}EnviarLoteEventos" % ns_envio, nsmap={None: ns_envio})
        lote = etree.SubElement(root, "{%s}loteEventos" % ns_envio)
        
        # eSocial Groups: 1 (Table), 2 (Non-periodical), 3 (Periodical)
        # S-1200 is Group 3 (Periodical). S-3000 is Group 2.
        # We'll detect from the first event in the list
        lote_group = "3" 
        if signed_event_xmls:
            if "evtRemun" in signed_event_xmls[0]: lote_group = "3"
            elif "evtExclusao" in signed_event_xmls[0]: lote_group = "2"
        
        esocial = etree.SubElement(lote, "{%s}eSocial" % ns_lote, nsmap={None: ns_lote})
        envio = etree.SubElement(esocial, "{%s}envioLoteEventos" % ns_lote)
        envio.set("grupo", lote_group) 
        
        ide_emp = etree.SubElement(envio, "{%s}ideEmpregador" % ns_lote)
        etree.SubElement(ide_emp, "{%s}tpInsc" % ns_lote).text = "1" # CNPJ
        etree.SubElement(ide_emp, "{%s}nrInsc" % ns_lote).text = nr_insc.replace(".", "").replace("-", "").replace("/", "")
        
        ide_trans = etree.SubElement(envio, "{%s}ideTransmissor" % ns_lote)
        etree.SubElement(ide_trans, "{%s}tpInsc" % ns_lote).text = "1" 
        etree.SubElement(ide_trans, "{%s}nrInsc" % ns_lote).text = nr_insc.replace(".", "").replace("-", "").replace("/", "")
        
        eventos = etree.SubElement(envio, "{%s}eventos" % ns_lote)
        
        for i, xml_str in enumerate(signed_event_xmls):
            # Parse signed XML to extract the Id
            item_xml = etree.fromstring(xml_str.encode('utf-8'))
            evt_id = item_xml.xpath("//@Id")[0]
            
            evt_node = etree.SubElement(eventos, "{%s}evento" % ns_lote)
            evt_node.set("Id", evt_id)
            
            # The individual eSocial event node goes here (it includes ds:Signature)
            evt_node.append(item_xml)

        return etree.tostring(root, encoding="utf-8", xml_declaration=False).decode('utf-8')

    def transmit_native(self, batch_content, url, cnpj_pattern, soap_action=None):
        """
        Uses native/transmitter.exe to send the SOAP payload using the A3 certificate.
        """
        if soap_action is None:
            soap_action = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0/ServicoEnviarLoteEventos/EnviarLoteEventos"

        temp_xml = os.path.join(tempfile.gettempdir(), f"batch_{uuid.uuid4().hex}.xml")
        with open(temp_xml, "w", encoding='utf-8') as f:
            f.write(batch_content)
        
        self.log(f"Iniciando transmissão...")
        try:
            # esocial_client.exe send <url> <xmlPath> <cnpj> <soapAction>
            result = subprocess.run(
                [self.client_path, "send", url, temp_xml, cnpj_pattern, soap_action], 
                capture_output=True, 
                text=True,
                encoding='latin1',
                errors='replace'
            )
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"ERRO na transmissão nativa (code {result.returncode}): {result.stdout or ''}\n{result.stderr or ''}"
        finally:
            if os.path.exists(temp_xml): os.remove(temp_xml)

    def sign_and_send_batch(self, xml_paths, nr_insc, tp_amb="2", grupo="3"):
        """
        Signs multiple events and sends as a batch in a SINGLE certificate session.
        Highly recommended to avoid multiple PIN prompts.
        """
        url = self.url_prod if tp_amb == "1" else self.url_homolog
        soap_action = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0/ServicoEnviarLoteEventos/EnviarLoteEventos"
        
        import re
        # S-1.3: Total cleaning of the ID
        nr_insc_clean = re.sub(r'\D', '', nr_insc)
        
        # S-1.3: In the Batch Envelope (EnviarLoteEventos), ideEmpregador MUST match the events.
        # For CNPJ, this means the 8-digit ROOT.
        nr_insc_root = nr_insc_clean[:8] if len(nr_insc_clean) > 11 else nr_insc_clean 

        # Command: sign-batch-send <url> <cert_pattern> <soapAction> <nrInscLote> <nrInscTransmissor> <grupo> <xmlPath1>...
        # nrInscLote will be 8 digits (root) to match events.
        # nrInscTransmissor will be 14 digits (full) to match the certificate.
        cmd = [self.client_path, "sign-batch-send", url, nr_insc_clean, soap_action, nr_insc_root, nr_insc_clean, str(grupo)] + xml_paths
        
        max_retries = 3
        last_error = ""

        for attempt in range(max_retries):
            try:
                self.log(f"Tentativa {attempt + 1}/{max_retries}...")
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='latin1', errors='replace')
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    # Success
                    return stdout
                else:
                    last_error = (stdout or "") + "\n" + (stderr or "")
                    if "503" in last_error or "cancelada" in last_error:
                        self.log(f"SERVIÇO INDISPONÍVEL (503/Timeout). Aguardando 5s para tentar novamente...")
                        time.sleep(5)
                        continue
                    else:
                        break # Other error, don't retry
            except Exception as e:
                last_error = str(e)
                time.sleep(2)

        return f"FALHA APÓS {max_retries} TENTATIVAS: {last_error}"

    def parse_response(self, xml_str):
        """
        Parses the eSocial SOAP response to extract status code, description, and protocol.
        """
        if not xml_str:
            return {"status": "ERRO", "desc": "Resposta vazia", "protocol": "", "errors": ["Servidor do governo retornou corpo vazio."]}
        
        # Show Debug Info if found in output
        if "HTTP_ERROR" in xml_str or "EXCEPTION" in xml_str:
             return {"status": "ERRO", "desc": "Falha na Transmissão", "protocol": "", "errors": [xml_str.strip()]}
            
        try:
            # Clean up raw output from C# (Find the actual XML start)
            idx = xml_str.find("<")
            if idx >= 0: 
                xml_str = xml_str[idx:]
            else:
                # No XML found but we have status info
                if "DEBUG_HTTP_STATUS" in xml_str:
                     return {"status": "HTTP_INFO", "desc": xml_str.strip(), "protocol": "", "errors": ["Corpo XML não encontrado na resposta."], "event_results": []}

            # Note: Server might use different prefixes (s:, ns:, etc.)
            # We parse ignoring namespaces or using wildcards
            tree = etree.fromstring(xml_str.encode('utf-8'))
            
            # Check for SOAP Fault (Technical error in the server)
            faults = tree.xpath("//*[local-name()='Fault']")
            if faults:
                fault_string = faults[0].xpath(".//*[local-name()='faultstring']")[0].text if faults[0].xpath(".//*[local-name()='faultstring']") else "Erro desconhecido"
                if "ActionNotSupported" in fault_string:
                    return {"status": "FAULT", "desc": "Erro Técnico: Ação não suportada pelo servidor (SOAPAction incorreta).", "protocol": "", "errors": [fault_string], "event_results": []}
                return {"status": "FAULT", "desc": f"Erro Técnico no eSocial: {fault_string}", "protocol": "", "errors": [], "event_results": []}
            
            # Helper to find text ignoring namespaces
            def find_text(xpath):
                # Search by local name to ignore prefixes
                nodes = tree.xpath(f"//*[local-name()='{xpath}']")
                return nodes[0].text if nodes else ""

            cd = find_text("cdResposta")
            desc = find_text("descResposta")
            prot = find_text("protocoloEnvio")
            
            occurrences = []
            occ_nodes = tree.xpath("//*[local-name()='ocorrencia']")
            for occ in occ_nodes:
                e_cd = occ.xpath(".//*[local-name()='codigo']")[0].text if occ.xpath(".//*[local-name()='codigo']") else ""
                e_desc = occ.xpath(".//*[local-name()='descricao']")[0].text if occ.xpath(".//*[local-name()='descricao']") else ""
                occurrences.append(f"[{e_cd}] {e_desc}")

            # Capture individual event results if present (common in consultation)
            event_results = []
            events_nodes = tree.xpath("//*[local-name()='retornoEvento']")
            for node in events_nodes:
                evt_id = node.get("Id", "") # Atributo Id
                cd_res = node.xpath(".//*[local-name()='cdResposta']")[0].text if node.xpath(".//*[local-name()='cdResposta']") else ""
                desc_res = node.xpath(".//*[local-name()='descResposta']")[0].text if node.xpath(".//*[local-name()='descResposta']") else ""
                nr_rec = node.xpath(".//*[local-name()='nrRecibo']")[0].text if node.xpath(".//*[local-name()='nrRecibo']") else ""
                
                # S-1.3: Extraindo o XML de retorno completo (onde ficam os totalizadores S-5001/S-5011)
                raw_xml = etree.tostring(node, encoding='unicode', pretty_print=True)

                event_results.append({
                    "id": evt_id,
                    "status": cd_res,
                    "desc": desc_res,
                    "nr_recibo": nr_rec,
                    "retorno_xml": raw_xml
                })

            return {
                "status": cd,
                "desc": desc,
                "protocol": prot,
                "errors": occurrences,
                "event_results": event_results
            }
        except Exception as e:
            if "HTTP_ERROR" in str(xml_str):
                return {"status": "HTTP_ERROR", "desc": str(xml_str).strip(), "protocol": "", "errors": [], "event_results": []}
            if "ERRO na transmissão" in str(xml_str) or "ERROR_CERT" in str(xml_str):
                return {"status": "NETWORK_ERROR", "desc": "Falha de conexão ou certificado.", "protocol": "", "errors": [str(xml_str)], "event_results": []}
            return {"status": "PARSER_ERROR", "desc": f"Falha ao ler XML: {e}", "protocol": None, "errors": [str(xml_str)[:500]], "event_results": []}

    def sign_event(self, xml_content, cnpj_pattern):
        temp_xml = os.path.join(tempfile.gettempdir(), f"evt_{uuid.uuid4().hex}.xml")
        with open(temp_xml, "w", encoding='utf-8') as f:
            f.write(xml_content)
        
        try:
            # esocial_client.exe sign <xmlPath> <cnpj>
            res = subprocess.run(
                [self.client_path, "sign", temp_xml, cnpj_pattern], 
                capture_output=True, 
                text=True,
                encoding='latin1',
                errors='replace'
            )
            if res.returncode == 0:
                signed_path = temp_xml + ".signed"
                with open(signed_path, "r", encoding='utf-8') as f:
                    signed_xml = f.read()
                if os.path.exists(signed_path): os.remove(signed_path)
                return signed_xml
            else:
                raise Exception(f"Erro na assinatura: {res.stdout}")
        finally:
            if os.path.exists(temp_xml): os.remove(temp_xml)

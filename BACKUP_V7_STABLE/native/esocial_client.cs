using System;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography.X509Certificates;
using System.Security.Cryptography.Xml;
using System.Threading.Tasks;
using System.Text;
using System.Xml;
using System.Collections.Generic;

namespace ESocialClient {
    class Program {
        static int Main(string[] args) {
            if (args.Length < 2) {
                Console.WriteLine("Usage: esocial_client.exe <command> [args...]");
                Console.WriteLine("Commands:");
                Console.WriteLine("  sign <xmlPath> <cnpj>                       - Signs an event XML");
                Console.WriteLine("  send <url> <xmlPath> <cnpj> <soapAction>    - Sends a raw XML");
                Console.WriteLine("  sign-send <url> <xmlPath> <cnpj> <soapAct>  - Signs then Sends");
                return 1;
            }

            string command = args[0].ToLower();
            try {
                // Force TLS 1.2
                System.Net.ServicePointManager.SecurityProtocol = (System.Net.SecurityProtocolType)3072;

                if (command == "sign") return RunSign(args[1], args[2]);
                if (command == "send") return RunSend(args[1], args[2], args[3], args[4]);
                if (command == "sign-send") return RunSignSend(args[1], args[2], args[3], args[4]);
                if (command == "sign-batch-send") {
                    // sign-batch-send <url> <cnpj> <soapAction> <nrInscLote> <grupo> <eventXmlPath1> <eventXmlPath2> ...
                    return RunSignBatchSend(args);
                }

                Console.WriteLine("Unknown command: " + command);
                return 1;
            } catch (Exception ex) {
                Console.WriteLine("EXCEPTION: " + ex.Message);
                if (ex.InnerException != null) Console.WriteLine("INNER: " + ex.InnerException.Message);
                Console.WriteLine("STACK: " + ex.StackTrace);
                return 99;
            }
        }

        static int RunSign(string xmlPath, string cnpj) {
            X509Certificate2 cert = FindCertificate(cnpj);
            if (cert == null) { Console.WriteLine("ERROR: Certificate not found for " + cnpj); return 2; }

            XmlDocument doc = new XmlDocument() { PreserveWhitespace = true };
            doc.Load(xmlPath);
            SignXml(doc, cert);
            string outputPath = xmlPath + ".signed";
            doc.Save(outputPath);
            Console.WriteLine("SUCCESS_SIGN: " + outputPath);
            return 0;
        }

        static int RunSend(string url, string xmlPath, string cnpj, string soapAction) {
            X509Certificate2 cert = FindCertificate(cnpj);
            if (cert == null) { Console.WriteLine("ERROR: Certificate not found for " + cnpj); return 2; }

            string xmlContent = File.ReadAllText(xmlPath);
            return Transmit(url, xmlContent, cert, soapAction);
        }

        static int RunSignSend(string url, string xmlPath, string cnpj, string soapAction) {
            X509Certificate2 cert = FindCertificate(cnpj);
            if (cert == null) { Console.WriteLine("ERROR: Certificate not found for " + cnpj); return 2; }

            // 1. Sign
            XmlDocument doc = new XmlDocument() { PreserveWhitespace = true };
            doc.Load(xmlPath);
            SignXml(doc, cert);
            
            // 2. Transmit string from signed doc
            string xmlContent = doc.OuterXml;
            return Transmit(url, xmlContent, cert, soapAction);
        }

        static int RunSignBatchSend(string[] args) {
            try {
                string url = args[1];
                string certCnpj = args[2];
                string soapAction = args[3];
                string nrInscLote = args[4];
                string nrInscTransmissor = args[5];
                string grupo = args[6];
                
                // For S-1.3 Employer identification, we use the 8-digit root if provided
                // This matches the S-1000 already present in the portal.
                string nrInscLoteFull = nrInscLote;
                
                X509Certificate2 cert = FindCertificate(certCnpj);
                if (cert == null) { Console.WriteLine("ERROR_CERT: Not found " + certCnpj); return 2; }

                StringBuilder eventsXml = new StringBuilder();
                for (int i = 7; i < args.Length; i++) {
                    string path = args[i];
                    XmlDocument eventDoc = new XmlDocument() { PreserveWhitespace = true };
                    eventDoc.Load(path);
                    SignXml(eventDoc, cert);
                    
                    // eSocial Individual Event wrapped in <evento> tag for batch
                    // In S-1.3, the Id attribute is on the child (e.g. evtRemun), not on the root <eSocial>
                    string evtId = eventDoc.DocumentElement.GetAttribute("Id");
                    if (string.IsNullOrEmpty(evtId) && eventDoc.DocumentElement.HasChildNodes) {
                        var evtNode = eventDoc.DocumentElement.FirstChild as XmlElement;
                        if (evtNode != null) evtId = evtNode.GetAttribute("Id");
                    }

                    if (string.IsNullOrEmpty(evtId)) {
                        XmlNamespaceManager nsMgr = new XmlNamespaceManager(eventDoc.NameTable);
                        nsMgr.AddNamespace("e", eventDoc.DocumentElement.NamespaceURI);
                        var idAttr = eventDoc.SelectSingleNode("//@Id", nsMgr);
                        if (idAttr != null) evtId = idAttr.Value;
                    }

                    if (string.IsNullOrEmpty(evtId)) {
                         // Last resort, search anything called Id
                         var idAttr = eventDoc.SelectSingleNode("//@Id");
                         if (idAttr != null) evtId = idAttr.Value;
                    }

                    Console.WriteLine(string.Format("INFO: Preparando Evento ID: {0}", evtId));

                    // Each event MUST be wrapped in its own <eSocial> tag (OuterXml)
                    eventsXml.AppendFormat("<evento Id=\"{0}\">{1}</evento>", evtId, eventDoc.DocumentElement.OuterXml);
                }

                string tpInscLote = (nrInscLote.Length == 8 || nrInscLote.Length == 14) ? "1" : "2";
                string tpInscTrans = (nrInscTransmissor.Length == 8 || nrInscTransmissor.Length == 14) ? "1" : "2";

                string serviceNs = "http://www.esocial.gov.br/servicos/empregador/lote/eventos/envio/v1_1_0";
                string batchXml = string.Format(
                    "<ns:EnviarLoteEventos xmlns:ns=\"{3}\"><ns:loteEventos><eSocial xmlns=\"http://www.esocial.gov.br/schema/lote/eventos/envio/v1_1_1\"><envioLoteEventos grupo=\"{0}\"><ideEmpregador><tpInsc>{4}</tpInsc><nrInsc>{1}</nrInsc></ideEmpregador><ideTransmissor><tpInsc>{5}</tpInsc><nrInsc>{6}</nrInsc></ideTransmissor><eventos>{2}</eventos></envioLoteEventos></eSocial></ns:loteEventos></ns:EnviarLoteEventos>",
                    grupo.Trim(), nrInscLote.Trim().Substring(0, 8), eventsXml.ToString(), serviceNs, tpInscLote, tpInscTrans, nrInscTransmissor.Trim());

                // DEBUG LOGGING
                try {
                    File.WriteAllText("last_soap_request.xml", batchXml);
                    Console.WriteLine("DEBUG: SOAP guardado em last_soap_request.xml");
                } catch {}

                return Transmit(url, batchXml, cert, soapAction);
            } catch (Exception ex) {
                Console.WriteLine("BATCH_EXCEPTION: " + ex.Message);
                return 99;
            }
        }

        static int Transmit(string url, string xmlBody, X509Certificate2 cert, string soapAction) {
            // Build Envelope if needed
            if (!xmlBody.Contains("soapenv:Envelope")) {
                xmlBody = string.Format("<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\">\n <soapenv:Header/>\n <soapenv:Body>\n {0}\n </soapenv:Body>\n</soapenv:Envelope>", xmlBody);
            }

            var handler = new HttpClientHandler();
            handler.ClientCertificates.Add(cert);
            handler.ServerCertificateCustomValidationCallback = (m, c, ch, e) => true;

            using (var client = new HttpClient(handler)) {
                client.Timeout = TimeSpan.FromSeconds(120);
                var request = new HttpRequestMessage(HttpMethod.Post, url);
                // Wrap SOAPAction in double quotes as required by many government servers
                request.Headers.Add("SOAPAction", "\"" + soapAction + "\"");
                request.Content = new StringContent(xmlBody, Encoding.UTF8, "text/xml");

                try {
                    var response = client.SendAsync(request).Result;
                    string responseBody = response.Content.ReadAsStringAsync().Result;

                    Console.WriteLine(string.Format("DEBUG_HTTP_STATUS: {0}", (int)response.StatusCode));
                    
                    if (response.IsSuccessStatusCode) {
                        if (string.IsNullOrEmpty(responseBody)) {
                            Console.WriteLine("DEBUG_EMPTY_BODY: The server returned a success status but no XML content.");
                        }
                        Console.WriteLine(responseBody);
                        return 0;
                    } else {
                        Console.WriteLine(string.Format("HTTP_ERROR_{0}: {1}", (int)response.StatusCode, response.ReasonPhrase));
                        Console.WriteLine(responseBody);
                        return 3;
                    }
                } catch (AggregateException ae) {
                    foreach (var ex in ae.InnerExceptions) {
                        Console.WriteLine("TRANSMIT_EXCEPTION: " + ex.Message);
                    }
                    return 4;
                } catch (Exception ex) {
                    Console.WriteLine("TRANSMIT_EXCEPTION: " + ex.Message);
                    return 4;
                }
            }
        }

        static void SignXml(XmlDocument xmlDoc, X509Certificate2 cert) {
            // eSocial Event Signing logic (URI="")
            SignedXml signedXml = new SignedXml(xmlDoc);
            signedXml.SigningKey = cert.GetRSAPrivateKey();
            signedXml.SignedInfo.SignatureMethod = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256";

            Reference reference = new Reference();
            reference.Uri = ""; 
            reference.DigestMethod = "http://www.w3.org/2001/04/xmlenc#sha256";

            reference.AddTransform(new XmlDsigEnvelopedSignatureTransform());
            reference.AddTransform(new XmlDsigC14NTransform());

            signedXml.AddReference(reference);
            KeyInfo keyInfo = new KeyInfo();
            keyInfo.AddClause(new KeyInfoX509Data(cert));
            signedXml.KeyInfo = keyInfo;

            signedXml.ComputeSignature();
            XmlElement xmlDigitalSignature = signedXml.GetXml();
            xmlDoc.DocumentElement.AppendChild(xmlDoc.ImportNode(xmlDigitalSignature, true));
        }

        static X509Certificate2 FindCertificate(string cnpj) {
            string pattern = cnpj.Replace(".", "").Replace("-", "").Replace("/", "");
            X509Store store = new X509Store(StoreName.My, StoreLocation.CurrentUser);
            store.Open(OpenFlags.ReadOnly);
            foreach (var cert in store.Certificates) {
                if (cert.Subject.Contains(pattern) || (cert.FriendlyName != null && cert.FriendlyName.Contains(pattern))) {
                    return cert;
                }
            }
            return null;
        }
    }
}

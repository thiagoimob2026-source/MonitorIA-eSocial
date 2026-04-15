# VERSION: 2026-04-14-R7
import uuid
from datetime import datetime
from lxml import etree
import re

def _generate_evt_id(tp_insc, nr_insc):
    """Internal helper to generate standard eSocial ID."""
    full_nr = re.sub(r'\D', '', str(nr_insc))
    doc_id = full_nr[:8].ljust(14, '0') if str(tp_insc) == '1' else full_nr.zfill(14)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = str(uuid.uuid4().int)[:5]
    return f"ID{tp_insc}{doc_id}{timestamp}{rand}"

def generate_s1200_xml(data):
    """Generates XML for S-1200 version S-1.3."""
    ns = "http://www.esocial.gov.br/schema/evt/evtRemun/v_S_01_03_00"
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns})
    evt = etree.SubElement(root, "{%s}evtRemun" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns)
    etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = data.get('indRetif', '1')
    if data.get('nrRecEvt') and data.get('indRetif') == '2':
        etree.SubElement(ide_evt, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    etree.SubElement(ide_evt, "{%s}indApuracao" % ns).text = data.get('indApuracao', '1')
    etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', '')
    etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1')
    etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    
    ide_trab = etree.SubElement(evt, "{%s}ideTrabalhador" % ns)
    etree.SubElement(ide_trab, "{%s}cpfTrab" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    
    # [infoComplem] - Deve vir após cpfTrab no S-1.3
    if data.get('nmTrab') and data.get('dtNascto'):
        ic = etree.SubElement(ide_trab, "{%s}infoComplem" % ns)
        etree.SubElement(ic, "{%s}nmTrab" % ns).text = data.get('nmTrab')
        dnt = re.sub(r'\D', '', str(data.get('dtNascto', '')))
        if len(dnt) == 8:
            etree.SubElement(ic, "{%s}dtNascto" % ns).text = f"{dnt[4:]}-{dnt[2:4]}-{dnt[:2]}"
        else:
            etree.SubElement(ic, "{%s}dtNascto" % ns).text = data.get('dtNascto')

    for dm in data.get('demonstrativos', []):
        dm_dev = etree.SubElement(evt, "{%s}dmDev" % ns)
        etree.SubElement(dm_dev, "{%s}ideDmDev" % ns).text = dm.get('ideDmDev', '001')
        etree.SubElement(dm_dev, "{%s}codCateg" % ns).text = str(data.get('codCateg', '701'))
        
        # [infoPerApur] - Obrigatório vir ANTES de infoComplCont
        info_per = etree.SubElement(dm_dev, "{%s}infoPerApur" % ns); ide_est = etree.SubElement(info_per, "{%s}ideEstabLot" % ns)
        etree.SubElement(ide_est, "{%s}tpInsc" % ns).text = data.get('tpInscEstab', '1'); etree.SubElement(ide_est, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInscEstab', ''))).zfill(14); etree.SubElement(ide_est, "{%s}codLotacao" % ns).text = data.get('codLotacao', '1')
        remun = etree.SubElement(ide_est, "{%s}remunPerApur" % ns)
        if data.get('matricula'): etree.SubElement(remun, "{%s}matricula" % ns).text = data.get('matricula')
        for r in dm.get('rubrics', []):
            item = etree.SubElement(remun, "{%s}itensRemun" % ns); etree.SubElement(item, "{%s}codRubr" % ns).text = r.get('codRubr', ''); etree.SubElement(item, "{%s}ideTabRubr" % ns).text = r.get('ideTabRubr', 'contindi'); etree.SubElement(item, "{%s}vrRubr" % ns).text = "{:.2f}".format(float(r.get('vrRubr', 0))); etree.SubElement(item, "{%s}indApurIR" % ns).text = r.get('indApurIR', '0')
        
        # [infoComplCont] - Deve vir APÓS infoPerApur/infoPerAnt no S-1.3
        if data.get('nmTrab') and data.get('dtNascto'):
            icc = etree.SubElement(dm_dev, "{%s}infoComplCont" % ns)
            etree.SubElement(icc, "{%s}codCBO" % ns).text = str(data.get('codCBO', '214120'))

    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def generate_s1202_xml(data):
    """Generates XML for S-1202 version S-1.3."""
    ns = "http://www.esocial.gov.br/schema/evt/evtServRPPS/v_S_01_03_00"
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns})
    evt = etree.SubElement(root, "{%s}evtServRPPS" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns); etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = data.get('indRetif', '1')
    if data.get('nrRecEvt') and data.get('indRetif') == '2': etree.SubElement(ide_evt, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', ''); etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1'); etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    ide_trab = etree.SubElement(evt, "{%s}ideTrabalhador" % ns); etree.SubElement(ide_trab, "{%s}cpfTrab" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    for dm in data.get('demonstrativos', []):
        dm_dev = etree.SubElement(evt, "{%s}dmDev" % ns); etree.SubElement(dm_dev, "{%s}ideDmDev" % ns).text = dm.get('ideDmDev', '001'); etree.SubElement(dm_dev, "{%s}codCateg" % ns).text = str(data.get('codCateg', '301'))
        info_per = etree.SubElement(dm_dev, "{%s}infoPerApur" % ns); ide_est = etree.SubElement(info_per, "{%s}ideEstabLot" % ns); etree.SubElement(ide_est, "{%s}tpInsc" % ns).text = data.get('tpInscEstab', '1')
        etree.SubElement(ide_est, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInscEstab', ''))).zfill(14); etree.SubElement(ide_est, "{%s}codLotacao" % ns).text = data.get('codLotacao', '1'); remun = etree.SubElement(ide_est, "{%s}remunPerApur" % ns); etree.SubElement(remun, "{%s}matricula" % ns).text = data.get('matricula', '')
        for r in dm.get('rubrics', []):
            item = etree.SubElement(remun, "{%s}itensRemun" % ns); etree.SubElement(item, "{%s}codRubr" % ns).text = r.get('codRubr', ''); etree.SubElement(item, "{%s}ideTabRubr" % ns).text = r.get('ideTabRubr', 'contindi'); etree.SubElement(item, "{%s}vrRubr" % ns).text = "{:.2f}".format(float(r.get('vrRubr', 0)))
    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def generate_s1207_xml(data):
    """Generates XML for S-1207 version S-1.3."""
    ns = "http://www.esocial.gov.br/schema/evt/evtBeneficio/v_S_01_03_00"
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns}); evt = etree.SubElement(root, "{%s}evtBeneficio" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns); etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = data.get('indRetif', '1')
    if data.get('nrRecEvt') and data.get('indRetif') == '2': etree.SubElement(ide_evt, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', ''); etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1'); etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    ide_benef = etree.SubElement(evt, "{%s}ideBenef" % ns); etree.SubElement(ide_benef, "{%s}cpfBenef" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    for dm in data.get('demonstrativos', []):
        dm_dev = etree.SubElement(evt, "{%s}dmDev" % ns); etree.SubElement(dm_dev, "{%s}ideDmDev" % ns).text = dm.get('ideDmDev', '001'); info_per = etree.SubElement(dm_dev, "{%s}infoPerApur" % ns); ide_est = etree.SubElement(info_per, "{%s}ideEstabLot" % ns); etree.SubElement(ide_est, "{%s}tpInsc" % ns).text = data.get('tpInscEstab', '1')
        etree.SubElement(ide_est, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInscEstab', ''))).zfill(14); etree.SubElement(ide_est, "{%s}codLotacao" % ns).text = data.get('codLotacao', '1'); det = etree.SubElement(ide_est, "{%s}detComponentes" % ns); etree.SubElement(det, "{%s}nrBeneficio" % ns).text = data.get('matricula', '')
        for r in dm.get('rubrics', []):
            item = etree.SubElement(det, "{%s}itensRemun" % ns); etree.SubElement(item, "{%s}codRubr" % ns).text = r.get('codRubr', ''); etree.SubElement(item, "{%s}ideTabRubr" % ns).text = r.get('ideTabRubr', 'contindi'); etree.SubElement(item, "{%s}vrRubr" % ns).text = "{:.2f}".format(float(r.get('vrRubr', 0)))
    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def generate_s1210_xml(data):
    """Generates XML for S-1210 (evtPgtos) with Consolidation."""
    ns = "http://www.esocial.gov.br/schema/evt/evtPgtos/v_S_01_03_00"; evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns}); evt = etree.SubElement(root, "{%s}evtPgtos" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns); etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = data.get('indRetif', '1')
    if data.get('nrRecEvt') and data.get('indRetif') == '2': etree.SubElement(ide_evt, "{%s}nrRecibo" % ns).text = data.get('nrRecEvt', '')
    etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', ''); etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1'); etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    ide_benef = etree.SubElement(evt, "{%s}ideBenef" % ns); etree.SubElement(ide_benef, "{%s}cpfBenef" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    consolidated_pgtos = {}
    for pgto in data.get('pagamentos', []):
        dt_clean = re.sub(r'\D', '', str(pgto.get('dtPgto', ''))); dt_fmt = f"{dt_clean[4:]}-{dt_clean[2:4]}-{dt_clean[:2]}" if len(dt_clean) == 8 else pgto.get('dtPgto', '')
        key = (dt_fmt, pgto.get('tpPgto', '1'), pgto.get('perRef', '').strip())
        if key not in consolidated_pgtos: consolidated_pgtos[key] = {'dtPgto': dt_fmt, 'tpPgto': key[1], 'perRef': key[2], 'ideDmDevs': set(), 'vrLiq': 0.0}
        for dm in pgto.get('demonstrativos', []): consolidated_pgtos[key]['ideDmDevs'].add(dm.get('ideDmDev', '001'))
        try: consolidated_pgtos[key]['vrLiq'] += float(pgto.get('vrLiq') or 0)
        except: pass
    for key in sorted(consolidated_pgtos.keys()):
        pg = consolidated_pgtos[key]; info_pgto = etree.SubElement(ide_benef, "{%s}infoPgto" % ns); etree.SubElement(info_pgto, "{%s}dtPgto" % ns).text = pg['dtPgto']; etree.SubElement(info_pgto, "{%s}tpPgto" % ns).text = pg['tpPgto']
        if pg['perRef']: etree.SubElement(info_pgto, "{%s}perRef" % ns).text = pg['perRef']
        for dm_id in sorted(list(pg['ideDmDevs'])): etree.SubElement(info_pgto, "{%s}ideDmDev" % ns).text = dm_id
        etree.SubElement(info_pgto, "{%s}vrLiq" % ns).text = "{:.2f}".format(pg['vrLiq'])
    consolidated_ir = {}
    for pgto in data.get('pagamentos', []):
        cr = pgto.get('cr', '').strip()
        if not cr: continue
        if cr not in consolidated_ir: consolidated_ir[cr] = {'cr': cr, 'vrIRRF': 0.0, 'cpfDep': pgto.get('cpfDep', '').strip(), 'vlrDedDep': 0.0}
        try: consolidated_ir[cr]['vrIRRF'] += float(pgto.get('vrIRRF') or 0)
        except: pass
        try: consolidated_ir[cr]['vlrDedDep'] += float(pgto.get('vlrDedDep') or 0)
        except: pass
    if consolidated_ir:
        info_ir = etree.SubElement(ide_benef, "{%s}infoIRComplem" % ns)
        for cr in sorted(consolidated_ir.keys()):
            ir = consolidated_ir[cr]; info_cr = etree.SubElement(info_ir, "{%s}infoIRCR" % ns); etree.SubElement(info_cr, "{%s}tpCR" % ns).text = ir['cr']
            if ir['vrIRRF'] > 0: etree.SubElement(info_cr, "{%s}vrIRRF" % ns).text = "{:.2f}".format(ir['vrIRRF'])
            if ir['cpfDep'] and ir['vlrDedDep'] > 0:
                ded = etree.SubElement(info_cr, "{%s}dedDepen" % ns); etree.SubElement(ded, "{%s}tpRend" % ns).text = "11"; etree.SubElement(ded, "{%s}cpfDep" % ns).text = re.sub(r'\D', '', ir['cpfDep']).zfill(11); etree.SubElement(ded, "{%s}vlrDedDep" % ns).text = "{:.2f}".format(ir['vlrDedDep'])
    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def parse_esocial_xml(xml_content):
    """Robust parser for eSocial XMLs (Supports S-1200, 1202, 1207, 1210)."""
    def gtxt(node, path, default=""):
        """Safe text extraction with fallback."""
        try:
            res = node.xpath(path)
            if res and res[0] is not None:
                txt = res[0].text
                return txt if txt is not None else default
            return default
        except: return default

    try:
        xml_content = xml_content.strip()
        if xml_content.startswith('\ufeff'): xml_content = xml_content[1:]
        root = etree.fromstring(xml_content.encode('utf-8'))
        
        # Identify core event node
        nodes_ide = root.xpath("//*[local-name()='ideEvento']")
        if not nodes_ide:
            nodes_evt = root.xpath("//*[starts-with(local-name(), 'evt')]")
            target_node = nodes_evt[0] if nodes_evt else root
        else:
            target_node = nodes_ide[0].getparent()
        
        ename = target_node.tag.split('}')[-1]
        type_map = {'evtRemun': 'S-1200', 'evtServRPPS': 'S-1202', 'evtBeneficio': 'S-1207', 'evtPgtos': 'S-1210', 'evtExcl': 'S-3000'}
        info = {'type': type_map.get(ename, ename), 'demonstrativos': [], 'pagamentos': []}
        
        # Populate Header
        info['indRetif'] = gtxt(target_node, ".//*[local-name()='indRetif']", "1")
        info['perApur'] = gtxt(target_node, ".//*[local-name()='perApur']", "")
        info['nrRecEvt'] = gtxt(target_node, ".//*[local-name()='nrRecEvt' or local-name()='nrRecibo']", "")
        info['cpfTrab'] = gtxt(target_node, ".//*[local-name()='cpfTrab' or local-name()='cpfBenef']", "")
        
        # S-1200 Complementary Info
        info['nmTrab'] = gtxt(target_node, ".//*[local-name()='nmTrab']", "")
        info['dtNascto'] = gtxt(target_node, ".//*[local-name()='dtNascto']", "")
        info['codCBO'] = gtxt(target_node, ".//*[local-name()='codCBO']", "")

        # Extraction logic
        for dm in target_node.xpath(".//*[local-name()='dmDev']"):
            d_data = {'ideDmDev': gtxt(dm, ".//*[local-name()='ideDmDev']", "001"), 'rubrics': []}
            info['codCateg'] = gtxt(dm, ".//*[local-name()='codCateg']", "701")
            for rub in dm.xpath(".//*[local-name()='itensRemun']"):
                d_data['rubrics'].append({
                    'codRubr': gtxt(rub, ".//*[local-name()='codRubr']", ""),
                    'vrRubr': gtxt(rub, ".//*[local-name()='vrRubr']", "0.00"),
                    'ideTabRubr': gtxt(rub, ".//*[local-name()='ideTabRubr']", "contindi")
                })
            info['demonstrativos'].append(d_data)
        
        for ip in target_node.xpath(".//*[local-name()='infoPgto']"):
            p_data = {
                'dtPgto': gtxt(ip, ".//*[local-name()='dtPgto']", ""),
                'tpPgto': gtxt(ip, ".//*[local-name()='tpPgto']", "1"),
                'perRef': gtxt(ip, ".//*[local-name()='perRef']", ""),
                'vrLiq': gtxt(ip, ".//*[local-name()='vrLiq']", "0.00"),
                'demonstrativos': []
            }
            if p_data['dtPgto']:
                rd = re.sub(r'\D', '', p_data['dtPgto'])
                if len(rd) == 8: p_data['dtPgto'] = rd[6:8] + rd[4:6] + rd[0:4]
            for dmd in ip.xpath(".//*[local-name()='ideDmDev']"):
                p_data['demonstrativos'].append({'ideDmDev': dmd.text if dmd is not None else ""})
            info['pagamentos'].append(p_data)
        
        for ir in target_node.xpath(".//*[local-name()='infoIRCR']"):
            if info['pagamentos']:
                info['pagamentos'][0]['cr'] = gtxt(ir, ".//*[local-name()='tpCR']", "")
                info['pagamentos'][0]['vrIRRF'] = gtxt(ir, ".//*[local-name()='vrIRRF']", "0.00")
                info['pagamentos'][0]['cpfDep'] = gtxt(ir, ".//*[local-name()='cpfDep']", "")
                info['pagamentos'][0]['vlrDedDep'] = gtxt(ir, ".//*[local-name()='vlrDedDep']", "0.00")
        return info
    except Exception as e:
        print(f"DEBUG: parse_esocial_xml failed: {e}")
        return None

def generate_s3000_xml(data):
    """Generates XML for S-3000 (Exclusao)."""
    ns = "http://www.esocial.gov.br/schema/evt/evtExcl/v_S_01_03_00"; evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns}); evt = etree.SubElement(root, "{%s}evtExcl" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns); etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1'); etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    info_excl = etree.SubElement(evt, "{%s}infoExcl" % ns); etree.SubElement(info_excl, "{%s}tpEvento" % ns).text = data.get('tpEvento', 'S-1200'); etree.SubElement(info_excl, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    ide_trab = etree.SubElement(info_excl, "{%s}ideTrabalhador" % ns); etree.SubElement(ide_trab, "{%s}cpfTrab" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def generate_s1000_xml(data):
    """Generates XML for S-1000 version S-1.3."""
    ns = "http://www.esocial.gov.br/schema/evt/evtInfoEmpregador/v_S_01_03_00"; full_nr = re.sub(r'\D', '', str(data.get('nrInsc', ''))); timestamp = datetime.now().strftime("%Y%m%d%H%M%S"); evt_id = f"ID{data.get('tpInsc', '1')}{full_nr.ljust(14, '0')}{timestamp}{str(uuid.uuid4().int)[:5]}"
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns}); evt = etree.SubElement(root, "{%s}evtInfoEmpregador" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns); etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1'); etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = full_nr[:8]
    info_emp = etree.SubElement(evt, "{%s}infoEmpregador" % ns); inclusao = etree.SubElement(info_emp, "{%s}inclusao" % ns); ide_per = etree.SubElement(inclusao, "{%s}idePeriodo" % ns); etree.SubElement(ide_per, "{%s}iniValid" % ns).text = data.get('iniValid', '')
    info_cmpl = etree.SubElement(inclusao, "{%s}infoCadastro" % ns); etree.SubElement(info_cmpl, "{%s}classTrib" % ns).text = data.get('classTrib', '85'); etree.SubElement(info_cmpl, "{%s}indCoop" % ns).text = data.get('indCoop', '0'); etree.SubElement(info_cmpl, "{%s}indConstr" % ns).text = data.get('indConstr', '0'); etree.SubElement(info_cmpl, "{%s}indDesFolha" % ns).text = data.get('indDesFolha', '0'); etree.SubElement(info_cmpl, "{%s}indOpcCP" % ns).text = data.get('indOpcCP', '1'); etree.SubElement(info_cmpl, "{%s}indOptRegEletron" % ns).text = data.get('indOptRegEletron', '1')
    contato = etree.SubElement(info_cmpl, "{%s}contato" % ns); etree.SubElement(contato, "{%s}nmCtt" % ns).text = data.get('nmCtt', ''); etree.SubElement(contato, "{%s}cpfCtt" % ns).text = data.get('cpfCtt', '')
    return etree.tostring(root, encoding="utf-8", xml_declaration=False, pretty_print=True).decode('utf-8')

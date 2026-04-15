# VERSION: 2026-04-15-R1
import uuid
import os
from datetime import datetime
from lxml import etree
import re
import json
from pathlib import Path

# ============================= WRAPPER CENTRAL =============================
def generate_event_xml(evt_type: str, data: dict) -> str:
    """
    Central orchestrator for eSocial XML generation.

    Strategy (priority order):
      1. Hardcoded generators  — battle-tested, XSD-compliant for complex events.
      2. Dynamic JSON engine   — used for future events without a dedicated generator.

    NOTE: JSON layout files (layouts/*.json) serve the UI form builder (LayoutEngine).
    They are NOT the primary XML engine for events with a hardcoded generator.

    Args:
        evt_type: Event code, e.g. 'S-1200', 'S-1210', 'S-3000'.
        data:     Dictionary with all event data fields.
    Returns:
        XML string (UTF-8 encoded).
    """
    # Priority 1: Hardcoded generators (XSD-validated for very high complexity or special consolidation)
    _hardcoded = {
        "S-1210": generate_s1210_xml, # Keep S-1210 as hardcoded due to complex payment consolidation
        "S-1000": generate_s1000_xml,
    }
    generator = _hardcoded.get(evt_type)
    if generator:
        return generator(data)

    # Priority 2: Dynamic JSON engine (for future events without a hardcoded generator)
    layouts_dir = Path(__file__).parent / "layouts"
    layout_file = layouts_dir / f"{evt_type}.json"
    if layout_file.exists():
        with open(layout_file, encoding="utf-8") as f:
            layout = json.load(f)
        return generate_xml_from_metadata(layout, data)

    raise ValueError(
        f"generate_event_xml: sem suporte para evento '{evt_type}'. "
        f"Crie um arquivo layouts/{evt_type}.json ou implemente um generator hardcoded."
    )
# ===========================================================================

def generate_xml_from_metadata(layout, data):
    """
    Enhanced engine to generate eSocial XML based on a Layout Metadata (JSON).
    Handles tag ordering, namespaces, data formatting, and REPEATING groups.
    """
    evt_type = layout["event"]

    # Map human-readable version to the exact namespace suffix used by the gov portal
    VERSION_NS_SUFFIX = {
        "S-1.3": "S_01_03_00",
        "S-1.2": "S_01_02_00",
        "S-1.1": "S_01_01_00",
        "S-1.0": "S_01_00_00",
    }
    raw_version = layout.get("version", "S-1.3")
    version_tag = VERSION_NS_SUFFIX.get(raw_version, raw_version.replace(".", "_").replace("-", "_"))
    
    ns_map = {
        # Namespaces confirmados contra os XSDs oficiais de 2026-04-27 (gov.br)
        "S-1000": f"http://www.esocial.gov.br/schema/evt/evtInfoEmpregador/v_{version_tag}",
        "S-1200": f"http://www.esocial.gov.br/schema/evt/evtRemun/v_{version_tag}",
        "S-1202": f"http://www.esocial.gov.br/schema/evt/evtRmnRPPS/v_{version_tag}",
        "S-1207": f"http://www.esocial.gov.br/schema/evt/evtBenPrRP/v_{version_tag}",
        "S-1210": f"http://www.esocial.gov.br/schema/evt/evtPgtos/v_{version_tag}",
        "S-3000": f"http://www.esocial.gov.br/schema/evt/evtExclusao/v_{version_tag}"
    }
    
    ns = ns_map.get(evt_type, "")
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns})
    evt_node = etree.SubElement(root, "{%s}%s" % (ns, layout["xml_structure"]["root"]))
    evt_node.set("Id", evt_id)
    
    def evaluate_conditions(group_name, structure, data):
        conditions = structure.get("conditions", {}).get(group_name)
        if not conditions:
            return True
        for if_empty in conditions.get("if_empty", []):
            if str(data.get(if_empty, "")).strip(): return False
        for if_not_empty in conditions.get("if_not_empty", []):
            if not str(data.get(if_not_empty, "")).strip(): return False
        for k, v in conditions.get("if_startswith", {}).items():
            val = str(data.get(k, ""))
            if isinstance(v, list):
                if not any(val.startswith(x) for x in v): return False
            elif not val.startswith(v): return False
        for k, v in conditions.get("if_in", {}).items():
            if str(data.get(k, "")) not in v: return False
        return True

    def build_group(parent_node, group_name, structure, current_data):
        if not evaluate_conditions(group_name, structure, current_data):
            return
            
        if group_name not in structure["groups"]:
            return
            
        mappings = structure.get("mappings", {})
        
        for item in structure["groups"][group_name]:
            if not evaluate_conditions(item, structure, current_data):
                continue
                
            data_key = mappings.get(item, item)
            item_val = current_data.get(data_key)
            
            if item in structure["groups"]:
                # Nested Group or Repeating List
                if isinstance(item_val, list):
                    for sub_data in item_val:
                        # Merge data to pass down parent context (like codCateg, matricula) for conditions
                        merged = {**current_data, **sub_data}
                        if evaluate_conditions(item, structure, merged):
                            sub_node = etree.SubElement(parent_node, "{%s}%s" % (ns, item))
                            build_group(sub_node, item, structure, merged)
                else:
                    # Single Group
                    has_data = any(current_data.get(mappings.get(child, child)) is not None for child in structure["groups"].get(item, []))
                    if has_data or item == "infoPerApur" or item == "ideEstabLot": # Essential nodes
                        sub_node = etree.SubElement(parent_node, "{%s}%s" % (ns, item))
                        build_group(sub_node, item, structure, current_data)
            else:
                # Leaf Field
                val = current_data.get(data_key)
                if val is not None and str(val).strip() != "":
                    formatted_val = str(val).strip()
                    if "date" in item.lower() or "dt" in item.lower():
                        d = re.sub(r'\D', '', formatted_val)
                        if len(d) == 8: formatted_val = f"{d[4:]}-{d[2:4]}-{d[:2]}"
                    elif any(kw in item.lower() for kw in ["vlr", "vr", "valor"]):
                        try: formatted_val = "{:.2f}".format(float(formatted_val.replace(',', '.')))
                        except: pass
                    elif "cpf" in item.lower():
                        formatted_val = re.sub(r'\D', '', formatted_val).zfill(11)
                        
                    etree.SubElement(parent_node, "{%s}%s" % (ns, item)).text = formatted_val

    # 1. ideEvento
    ide_evt = etree.SubElement(evt_node, "{%s}ideEvento" % ns)
    if evt_type != "S-3000":
        etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = str(data.get('indRetif', '1'))
        if data.get('nrRecEvt') and str(data.get('indRetif')) == '2':
            etree.SubElement(ide_evt, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt')
    
    if data.get('indApuracao'):
        etree.SubElement(ide_evt, "{%s}indApuracao" % ns).text = str(data.get('indApuracao'))
    elif evt_type in ["S-1200", "S-1202", "S-1207"]:
        etree.SubElement(ide_evt, "{%s}indApuracao" % ns).text = "1" # Default Mensal
        
    if evt_type not in ["S-1000", "S-3000"]:
        etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', '')
    
    etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = str(data.get('tpAmb', '1'))
    etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"
    etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    
    # 2. ideEmpregador
    ide_emp = etree.SubElement(evt_node, "{%s}ideEmpregador" % ns)
    etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = str(data.get('tpInsc', '1'))
    etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]

    # 3. Dynamic Body - Handle sequences and top-level groups
    mappings = layout["xml_structure"].get("mappings", {})
    for item in layout["xml_structure"]["sequence"]:
        if item in ["ideEvento", "ideEmpregador"]: continue
        
        if not evaluate_conditions(item, layout["xml_structure"], data):
            continue
            
        data_key = mappings.get(item, item)
        item_data = data.get(data_key) or data
        
        if isinstance(item_data, list):
            for sub in item_data:
                merged = {**data, **sub}
                node = etree.SubElement(evt_node, "{%s}%s" % (ns, item))
                build_group(node, item, layout["xml_structure"], merged)
        else:
            node = etree.SubElement(evt_node, "{%s}%s" % (ns, item))
            build_group(node, item, layout["xml_structure"], data)

    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

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
    
    # [infoComplem] - SOMENTE para trabalhadores SEM matrícula e categoria autônoma (7xx)
    # Se já há registro S-2200/S-2300, este bloco NÃO deve ser enviado (erro 553)
    matricula = str(data.get('matricula', '') or '').strip()
    cod_categ = str(data.get('codCateg', '701') or '701').strip()
    is_autonomous = cod_categ.startswith('7') or cod_categ in ['701', '711', '712', '721', '722', '731', '734', '761']
    needs_infocomplem = (not matricula) and is_autonomous and data.get('nmTrab') and data.get('dtNascto')
    
    if needs_infocomplem:
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
        
        # [infoComplCont] - Deve vir APÓS infoPerApur no S-1.3
        # Só incluir quando infoComplem foi enviado (mesmo critério: autônomo sem matrícula)
        if needs_infocomplem and data.get('codCBO'):
            icc = etree.SubElement(dm_dev, "{%s}infoComplCont" % ns)
            etree.SubElement(icc, "{%s}codCBO" % ns).text = str(data.get('codCBO', '214120'))

    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def generate_s1202_xml(data):
    """Generates XML for S-1202 version S-1.3 (Servidores RPPS)."""
    ns = "http://www.esocial.gov.br/schema/evt/evtRmnRPPS/v_S_01_03_00"
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns})
    evt = etree.SubElement(root, "{%s}evtRmnRPPS" % ns)
    evt.set("Id", evt_id)
    # ideEvento: indRetif [nrRecEvt] indApuracao perApur tpAmb procEmi verProc
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns)
    etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = data.get('indRetif', '1')
    if data.get('nrRecEvt') and data.get('indRetif') == '2':
        etree.SubElement(ide_evt, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    etree.SubElement(ide_evt, "{%s}indApuracao" % ns).text = data.get('indApuracao', '1')
    etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', '')
    etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1')
    etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"
    etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns)
    etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1')
    etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    ide_trab = etree.SubElement(evt, "{%s}ideTrabalhador" % ns)
    etree.SubElement(ide_trab, "{%s}cpfTrab" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    for dm in data.get('demonstrativos', []):
        dm_dev = etree.SubElement(evt, "{%s}dmDev" % ns)
        etree.SubElement(dm_dev, "{%s}ideDmDev" % ns).text = dm.get('ideDmDev', '001')
        etree.SubElement(dm_dev, "{%s}codCateg" % ns).text = str(data.get('codCateg', '301'))
        # S-1202 XSD: infoPerApur > ideEstab > remunPerApur
        info_per = etree.SubElement(dm_dev, "{%s}infoPerApur" % ns)
        ide_est = etree.SubElement(info_per, "{%s}ideEstab" % ns)
        etree.SubElement(ide_est, "{%s}tpInsc" % ns).text = data.get('tpInscEstab', '1')
        etree.SubElement(ide_est, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInscEstab', ''))).zfill(14)
        etree.SubElement(ide_est, "{%s}codLotacao" % ns).text = data.get('codLotacao', '1')
        remun = etree.SubElement(ide_est, "{%s}remunPerApur" % ns)
        etree.SubElement(remun, "{%s}matricula" % ns).text = data.get('matricula', '')
        for r in dm.get('rubrics', []):
            item = etree.SubElement(remun, "{%s}itensRemun" % ns)
            etree.SubElement(item, "{%s}codRubr" % ns).text = r.get('codRubr', '')
            etree.SubElement(item, "{%s}ideTabRubr" % ns).text = r.get('ideTabRubr', 'contindi')
            etree.SubElement(item, "{%s}vrRubr" % ns).text = "{:.2f}".format(float(r.get('vrRubr', 0)))
    return etree.tostring(root, encoding="utf-8", pretty_print=True).decode('utf-8')

def generate_s1207_xml(data):
    """Generates XML for S-1207 version S-1.3."""
    ns = "http://www.esocial.gov.br/schema/evt/evtBenPrRP/v_S_01_03_00"
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns}); evt = etree.SubElement(root, "{%s}evtBenPrRP" % ns); evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns); etree.SubElement(ide_evt, "{%s}indRetif" % ns).text = data.get('indRetif', '1')
    if data.get('nrRecEvt') and data.get('indRetif') == '2': etree.SubElement(ide_evt, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    etree.SubElement(ide_evt, "{%s}perApur" % ns).text = data.get('perApur', ''); etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1'); etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"; etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns); etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1'); etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    ide_benef = etree.SubElement(evt, "{%s}ideBenef" % ns)
    etree.SubElement(ide_benef, "{%s}cpfBenef" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
    for dm in data.get('demonstrativos', []):
        dm_dev = etree.SubElement(evt, "{%s}dmDev" % ns)
        etree.SubElement(dm_dev, "{%s}ideDmDev" % ns).text = dm.get('ideDmDev', '001')
        # S-1207 XSD evtBenPrRP: dmDev > nrBeneficio > infoPerApur > ideEstab > detComponentes
        etree.SubElement(dm_dev, "{%s}nrBeneficio" % ns).text = data.get('matricula', '')
        info_per = etree.SubElement(dm_dev, "{%s}infoPerApur" % ns)
        ide_est = etree.SubElement(info_per, "{%s}ideEstab" % ns)
        etree.SubElement(ide_est, "{%s}tpInsc" % ns).text = data.get('tpInscEstab', '1')
        etree.SubElement(ide_est, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInscEstab', ''))).zfill(14)
        etree.SubElement(ide_est, "{%s}codLotacao" % ns).text = data.get('codLotacao', '1')
        det = etree.SubElement(ide_est, "{%s}detComponentes" % ns)
        for r in dm.get('rubrics', []):
            item = etree.SubElement(det, "{%s}itensRemun" % ns)
            etree.SubElement(item, "{%s}codRubr" % ns).text = r.get('codRubr', '')
            etree.SubElement(item, "{%s}ideTabRubr" % ns).text = r.get('ideTabRubr', 'contindi')
            etree.SubElement(item, "{%s}vrRubr" % ns).text = "{:.2f}".format(float(r.get('vrRubr', 0)))
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
        # Root tags alinhados com os XSDs S-1.3 oficiais
        type_map = {
            'evtRemun':       'S-1200',
            'evtRmnRPPS':     'S-1202',  # Nome correto em S-1.3 (era evtServRPPS em versões antigas)
            'evtBenPrRP':     'S-1207',  # Nome correto em S-1.3 (era evtBeneficio em versões antigas)
            'evtPgtos':       'S-1210',
            'evtExcl':        'S-3000',
            'evtInfoEmpregador': 'S-1000',
        }
        info = {'type': type_map.get(ename, ename), 'demonstrativos': [], 'pagamentos': []}
              # Core Mappings
        info['indRetif'] = gtxt(target_node, ".//*[local-name()='indRetif']", "1")
        info['perApur'] = gtxt(target_node, ".//*[local-name()='perApur']", "")
        info['nrRecEvt'] = gtxt(target_node, ".//*[local-name()='nrRecEvt' or local-name()='nrRecibo']", "")
        info['cpfTrab'] = gtxt(target_node, ".//*[local-name()='cpfTrab' or local-name()='cpfBenef']", "")
        
        # S-1200 / S-1202 Identification
        info['nmTrab'] = gtxt(target_node, ".//*[local-name()='nmTrab']", "")
        info['dtNascto'] = gtxt(target_node, ".//*[local-name()='dtNascto']", "")
        info['codCBO'] = gtxt(target_node, ".//*[local-name()='codCBO']", "")
        info['matricula'] = gtxt(target_node, ".//*[local-name()='matricula']", "")
        info['codCateg'] = gtxt(target_node, ".//*[local-name()='codCateg']", "")
        info['codLotacao'] = gtxt(target_node, ".//*[local-name()='codLotacao']", "")

        # Extraction logic for Demonstratives (S-1200, 1202, 1207)
        dms = target_node.xpath(".//*[local-name()='dmDev']")
        for dm in dms:
            d_data = {
                'ideDmDev': gtxt(dm, ".//*[local-name()='ideDmDev']", "001"),
                'rubrics': []
            }
            # Deep search for rubrics (itensRemun) within this demonstrative
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
    """Generates XML for S-3000 (Exclusao) version S-1.3."""
    ns = "http://www.esocial.gov.br/schema/evt/evtExclusao/v_S_01_03_00"
    evt_id = _generate_evt_id(data.get('tpInsc', '1'), data.get('nrInsc', ''))
    root = etree.Element("{%s}eSocial" % ns, nsmap={None: ns})
    # XSD evtExclusao: root event tag is 'evtExclusao' (not 'evtExcl')
    evt = etree.SubElement(root, "{%s}evtExclusao" % ns)
    evt.set("Id", evt_id)
    ide_evt = etree.SubElement(evt, "{%s}ideEvento" % ns)
    etree.SubElement(ide_evt, "{%s}tpAmb" % ns).text = data.get('tpAmb', '1')
    etree.SubElement(ide_evt, "{%s}procEmi" % ns).text = "1"
    etree.SubElement(ide_evt, "{%s}verProc" % ns).text = "1.0"
    ide_emp = etree.SubElement(evt, "{%s}ideEmpregador" % ns)
    etree.SubElement(ide_emp, "{%s}tpInsc" % ns).text = data.get('tpInsc', '1')
    etree.SubElement(ide_emp, "{%s}nrInsc" % ns).text = re.sub(r'\D', '', str(data.get('nrInsc', '')))[:8]
    info_excl = etree.SubElement(evt, "{%s}infoExclusao" % ns)
    etree.SubElement(info_excl, "{%s}tpEvento" % ns).text = data.get('tpEvento', 'S-1200')
    etree.SubElement(info_excl, "{%s}nrRecEvt" % ns).text = data.get('nrRecEvt', '')
    ide_trab = etree.SubElement(info_excl, "{%s}ideTrabalhador" % ns)
    etree.SubElement(ide_trab, "{%s}cpfTrab" % ns).text = re.sub(r'\D', '', str(data.get('cpfTrab', ''))).zfill(11)
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

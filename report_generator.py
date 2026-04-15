from fpdf import FPDF, XPos, YPos
from datetime import datetime
import re

try:
    from lxml import etree as ET
except ImportError:
    import xml.etree.ElementTree as ET


class ESocialReport(FPDF):
    # Brand colors
    COLOR_HEADER_BG = (30, 58, 92)
    COLOR_SUBHEADER  = (52, 152, 219)
    COLOR_SUCCESS    = (39, 174, 96)
    COLOR_ERROR      = (192, 57, 43)
    COLOR_PENDING    = (243, 156, 18)
    COLOR_ROW_ALT    = (245, 248, 252)

    def header(self):
        self.set_fill_color(*self.COLOR_HEADER_BG)
        self.rect(0, 0, 210, 20, 'F')
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(255, 255, 255)
        self.set_y(5)
        self.cell(0, 10, 'IA_eSocial Monitor  -  Relatorio Analitico de Transmissao', 0,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 5, f'Gerado em: {datetime.now().strftime("%d/%m/%Y  %H:%M:%S")}', 0,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='R')
        self.set_text_color(0, 0, 0)
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'IA_eSocial  |  Pagina {self.page_no()}/{{nb}}', 0,
                  new_x=XPos.RIGHT, new_y=YPos.TOP, align='C')
        self.set_text_color(0, 0, 0)

    # ------------------------------------------------------------------ helpers
    def _section_title(self, title):
        self.set_fill_color(*self.COLOR_SUBHEADER)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        self.ln(2)
        self.cell(0, 8, f'  {title}', 0,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def _status_color(self, status):
        s = str(status).lower()
        if 'aceito' in s or 'sucesso' in s or 'processado' in s:
            return self.COLOR_SUCCESS
        if 'erro' in s or 'falha' in s or 'rejeit' in s:
            return self.COLOR_ERROR
        return self.COLOR_PENDING

    def _cell(self, w, h, txt='', border=0, align='L', fill=False, ln=False):
        if ln:
            self.cell(w, h, str(txt).strip(), border, align=align, fill=fill,
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            self.cell(w, h, str(txt).strip(), border, align=align, fill=fill,
                      new_x=XPos.RIGHT, new_y=YPos.TOP)

    # ------------------------------------------------------------------ Resilient XML parsing
    def extract_s5001_data(self, xml_content):
        """Extracts comparison data from S-5001 XML (evt5001 or evtBasesTrab)."""
        result = {
            'cpf': '-', 'nome': '-', 'perApur': '-',
            'vlrESocial': 0.0, 'vlrFolha': 0.0, 'diferenca': 0.0
        }
        
        if not xml_content:
            return result
            
        try:
            xml_str = str(xml_content).strip()
            if not xml_str.startswith('<'):
                idx = xml_str.find('<')
                if idx >= 0: xml_str = xml_str[idx:]
            
            root = ET.fromstring(xml_str.encode('utf-8'))
            
            def get_local_name(node):
                return node.tag.split('}')[-1] if '}' in node.tag else node.tag

            def find_all(parent, tag_name):
                return [n for n in parent.iter() if get_local_name(n) == tag_name]

            def first_val(parent, tag_name):
                nodes = find_all(parent, tag_name)
                return nodes[0].text.strip() if nodes and nodes[0].text else None

            # Identification - search anywhere in the tree due to possible envelopes
            result['cpf'] = first_val(root, 'cpfTrab') or '-'
            result['nome'] = first_val(root, 'nmTrab') or '-'
            result['perApur'] = first_val(root, 'perApur') or '-'

            # calc_nodes handles both infoCpCalc and infoCp (depending on eSocial version)
            calc_nodes = find_all(root, 'infoCpCalc')
            total_esocial = 0.0
            total_folha = 0.0

            for node in calc_nodes:
                # eSocial Calculated
                v_esoc = first_val(node, 'vrCpSeg')
                if v_esoc: total_esocial += float(v_esoc)
                
                # Folha (In S-5001 vS-1.2/1.3, vrDescSeg is what the company reported)
                v_folha = first_val(node, 'vrDescSeg')
                if v_folha: 
                    total_folha += float(v_folha)
                else:
                    # Fallback if vrDescSeg is not present, try to find infoCp/vrCpSeg
                    # (older versions or different event types)
                    pass

            # If vrDescSeg wasn't found in infoCpCalc, try searching in infoCp explicitly
            if total_folha == 0:
                info_cp_nodes = find_all(root, 'infoCp')
                for node in info_cp_nodes:
                    v_cp = first_val(node, 'vrCpSeg')
                    if v_cp: total_folha += float(v_cp)

            result['vlrESocial'] = total_esocial
            result['vlrFolha'] = total_folha
            result['diferenca'] = round(total_esocial - total_folha, 2)

        except Exception as e:
            print(f"Erro ao extrair S-5001: {e}")
            
        return result

    def generate_s5001_report(self, data_list, output_path):
        """Generates a specialized comparison report for S-5001 events."""
        self.add_page()
        self.alias_nb_pages()

        # Title
        self.set_fill_color(240, 240, 240)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 12, 'Relatório de Conferência de INSS (S-5001)', 0, ln=True, align='C')
        self.ln(5)

        # Summary Header
        total_e = sum(d['vlrESocial'] for d in data_list)
        total_f = sum(d['vlrFolha'] for d in data_list)
        total_diff = total_e - total_f

        # Dashboard
        col_w = 60
        self.set_fill_color(30, 58, 92)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        self.cell(col_w, 8, 'Total eSocial', 1, 0, 'C', True)
        self.cell(col_w, 8, 'Total Folha', 1, 0, 'C', True)
        self.cell(col_w, 8, 'Diferença Total', 1, 1, 'C', True)

        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'B', 12)
        self.cell(col_w, 10, self._br(total_e), 1, 0, 'C')
        self.cell(col_w, 10, self._br(total_f), 1, 0, 'C')
        
        diff_color = self.COLOR_ERROR if abs(total_diff) > 0.01 else self.COLOR_SUCCESS
        self.set_text_color(*diff_color)
        self.cell(col_w, 10, self._br(total_diff), 1, 1, 'C')
        self.set_text_color(0, 0, 0)
        self.ln(10)

        # Table Header
        self.set_fill_color(*self.COLOR_HEADER_BG)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 8)
        self.cell(25, 8, 'CPF', border=1, align='C', fill=True)
        self.cell(60, 8, 'Nome', border=1, align='L', fill=True)
        self.cell(20, 8, 'Período', border=1, align='C', fill=True)
        self.cell(28, 8, 'vlr eSocial', border=1, align='R', fill=True)
        self.cell(28, 8, 'vlr Folha', border=1, align='R', fill=True)
        self.cell(0, 8, 'Diferença', border=1, align='R', fill=True, ln=True)
        self.set_text_color(0, 0, 0)

        # Data Rows
        self.set_font('Helvetica', '', 8)
        alternate = False
        for d in data_list:
            if self.get_y() > 270:
                self.add_page()
                # Repeat Header... (omitted for brevity in logic but good for production)
            
            bg = self.COLOR_ROW_ALT if alternate else (255, 255, 255)
            self.set_fill_color(*bg)
            
            self.cell(25, 7, d['cpf'], border=1, align='C', fill=True)
            self.cell(60, 7, self._safe(d['nome'], 35), border=1, align='L', fill=True)
            self.cell(20, 7, d['perApur'], border=1, align='C', fill=True)
            self.cell(28, 7, self._br(d['vlrESocial']), border=1, align='R', fill=True)
            self.cell(28, 7, self._br(d['vlrFolha']), border=1, align='R', fill=True)
            
            diff = d['diferenca']
            if abs(diff) > 0.01:
                self.set_text_color(*self.COLOR_ERROR)
                self.set_font('Helvetica', 'B', 8)
            else:
                self.set_text_color(*self.COLOR_SUCCESS)
            
            self.cell(0, 7, self._br(diff), border=1, align='R', fill=True, ln=True)
            self.set_text_color(0, 0, 0)
            self.set_font('Helvetica', '', 8)
            alternate = not alternate

        self.output(output_path)
        return output_path

    def _extract_xml_values(self, xml_content, evt_type):
        """Namespace-agnostic extraction focusing on basic worker/period data."""
        result = {'rubricas': [], 'perApur': None, 'matricula': None, 'nrRecBackup': None}
        
        if not xml_content or not str(xml_content).strip():
            return result
            
        try:
            xml_str = str(xml_content).strip()
            if not xml_str.startswith('<'):
                idx = xml_str.find('<')
                if idx >= 0: xml_str = xml_str[idx:]
                else: return result

            root = ET.fromstring(xml_str.encode('utf-8'))

            def get_local_name(node):
                return node.tag.split('}')[-1] if '}' in node.tag else node.tag

            def find_all(parent, tag_name):
                return [n for n in parent.iter() if get_local_name(n) == tag_name]

            def first_val(parent, tag_name):
                nodes = find_all(parent, tag_name)
                return nodes[0].text.strip() if nodes and nodes[0].text else None

            # Universal basic fields
            result['perApur']     = first_val(root, 'perApur')
            result['matricula']   = first_val(root, 'matricula') or first_val(root, 'nrBeneficio')
            result['nrRecBackup'] = first_val(root, 'nrRecEvt') or first_val(root, 'nrRecibo')

            if evt_type in ('S-1200', 'S-1202', 'S-1207'):
                remun_nodes = find_all(root, 'itensRemun')
                for item in remun_nodes:
                    cod = first_val(item, 'codRubr')
                    vr  = first_val(item, 'vrRubr')
                    if cod and vr:
                        result['rubricas'].append({'cod': cod, 'vr': vr})

        except Exception as e:
            result['parse_error'] = str(e)
            
        return result

    def _br(self, value):
        try:
            v = float(str(value).replace(',', '.'))
            return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except Exception:
            return f'R$ {value}'

    def _safe(self, text, max_len=None):
        s = str(text or '').strip().encode('latin-1', errors='replace').decode('latin-1')
        if max_len: s = s[:max_len]
        return s

    # ------------------------------------------------------------------ main report
    # ------------------------------------------------------------------ main report
    def generate_report(self, data, output_path, filters=None):
        self.add_page()
        self.alias_nb_pages()

        # ---- 1. DASHBOARD HEADER ----
        status_counts = {}
        for item in data:
            s = item.get('status', 'Desconhecido')
            status_counts[s] = status_counts.get(s, 0) + 1

        self.set_fill_color(240, 240, 240)
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Resumo Executivo de Transmissão', 0, ln=True, align='L')
        self.ln(2)

        # Draw summary boxes
        col_w = 40
        margin = 10
        start_x = self.get_x()
        for i, (status, count) in enumerate(status_counts.items()):
            r, g, b = self._status_color(status)
            self.set_draw_color(r, g, b)
            self.set_text_color(r, g, b)
            
            # Position for the next box
            box_x = start_x + (i * (col_w + 5))
            if box_x + col_w > 190: # Simple line break if too many status types
                box_x = start_x
                self.set_y(self.get_y() + 20)
                start_x = box_x
                
            y_base = self.get_y()
            self.set_xy(box_x, y_base)
            self.set_font('Helvetica', 'B', 14)
            self.cell(col_w, 10, str(count), border='TLR', align='C')
            
            self.set_xy(box_x, y_base + 10)
            self.set_font('Helvetica', '', 7)
            self.cell(col_w, 6, self._safe(status), border='BLR', align='C')
            self.set_xy(box_x + col_w + 5, y_base) # Ready for next or for line end
        
        self.set_text_color(0, 0, 0)
        self.set_y(self.get_y() + 22)
        self.ln(5)

        # ---- 2. FILTERS (Compact) ----
        if filters:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(100, 100, 100)
            filter_str = " | ".join([f"{k}: {v}" for k, v in filters.items() if v])
            self.cell(0, 5, f"Filtros: {self._safe(filter_str)}", ln=True)
            self.set_text_color(0, 0, 0)
            self.ln(5)

        # ---- 3. GROUP BY CPF ----
        by_cpf = {}
        for item in data:
            cpf = item.get('cpf', 'Não Identificado')
            by_cpf.setdefault(cpf, []).append(item)

        # Table Header
        self._set_table_header()

        for cpf, items in by_cpf.items():
            # Check for page break
            if self.get_y() > 260:
                self.add_page()
                self._set_table_header()

            # CPF Header Row
            self.set_fill_color(235, 240, 250)
            self.set_font('Helvetica', 'B', 9)
            # Try to find a name for this CPF in the events
            name = "-"
            for it in items:
                if it.get('nmTrab'): name = it.get('nmTrab')
                elif it.get('nome'): name = it.get('nome')
                if name != "-": break
            
            self.cell(0, 8, f" TRABALHADOR: {self._safe(cpf)} - {self._safe(name)}", border=1, fill=True, ln=True)

            self.set_font('Helvetica', '', 8)
            for item in items:
                evt_type = item.get('type', '-')
                xml_content = item.get('xml_content', '')
                vals = self._extract_xml_values(xml_content, evt_type)
                
                status = self._safe(item.get('status', '-'))
                recibo = self._safe(item.get('nr_recibo', '') or vals.get('nrRecBackup', '') or '-')
                period = self._safe(vals.get('perApur', '-') or '-')
                
                # Row content
                self.cell(25, 7, evt_type, border=1, align='C')
                self.cell(30, 7, period, border=1, align='C')
                
                r, g, b = self._status_color(status)
                self.set_text_color(r, g, b)
                self.cell(50, 7, status[:25], border=1, align='C')
                self.set_text_color(0, 0, 0)
                
                self.cell(0, 7, recibo[:60], border=1, ln=True)

            self.ln(2)

        self.output(output_path)
        return output_path

    def _set_table_header(self):
        self.set_fill_color(*self.COLOR_HEADER_BG)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 8)
        self.cell(25, 8, 'Evento', border=1, align='C', fill=True)
        self.cell(30, 8, 'Período', border=1, align='C', fill=True)
        self.cell(50, 8, 'Status', border=1, align='C', fill=True)
        self.cell(0, 8, 'Recibo / Protocolo', border=1, align='C', fill=True, ln=True)
        self.set_text_color(0, 0, 0)

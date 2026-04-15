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
    def generate_report(self, data, output_path, filters=None):
        self.add_page()
        self.alias_nb_pages()

        # ---- 1. FILTERS INFO ----
        if filters:
            self._section_title('Filtros Aplicados')
            self.set_font('Helvetica', '', 9)
            for k, v in filters.items():
                if v:
                    self._cell(60, 6, f'{k}:', align='R')
                    self._cell(0, 6, self._safe(v), ln=True)
            self.ln(4)

        # ---- 2. SUMMARY COUNTS ----
        self._section_title('Resumo por Status')
        status_counts = {}
        for item in data:
            s = item.get('status', 'Desconhecido')
            status_counts[s] = status_counts.get(s, 0) + 1

        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(220, 230, 240)
        self._cell(120, 8, 'Status', border=1, align='C', fill=True)
        self._cell(30,  8, 'Qtd',    border=1, align='C', fill=True, ln=True)

        self.set_font('Helvetica', '', 9)
        total_records = 0
        for status, count in status_counts.items():
            r, g, b = self._status_color(status)
            self.set_text_color(r, g, b)
            self._cell(120, 7, self._safe(status), border=1)
            self._cell(30,  7, str(count), border=1, align='C', ln=True)
            self.set_text_color(0, 0, 0)
            total_records += count
        self.ln(6)

        # ---- 3. PER-EVENT TYPE CARDS ----
        by_type = {}
        for item in data:
            t = item.get('type', 'Outros')
            by_type.setdefault(t, []).append(item)

        for evt_type, items in sorted(by_type.items()):
            self._section_title(f'Eventos {evt_type}  ({len(items)} registros)')

            for item in items:
                xml_content = item.get('xml_content', '')
                vals = self._extract_xml_values(xml_content, evt_type)
                rubrics_count = len(vals.get('rubricas', []))
                
                estimated_height = 30 + (rubrics_count * 6)
                if self.get_y() + estimated_height > 275:
                    self.add_page()

                # --- START CARD (Simplified) ---
                self.set_fill_color(252, 252, 252)
                self.set_draw_color(180, 180, 180)
                
                # Card Header
                self.set_fill_color(240, 245, 250)
                self.set_font('Helvetica', 'B', 9)
                self._cell(0, 8, f"  CPF: {self._safe(item.get('cpf', ''))}  -  Dados de Transmissao ({evt_type})", border='TLR', fill=True, ln=True)

                # Metrics Row
                self.set_font('Helvetica', '', 8)
                competencia = self._safe(vals.get('perApur', '-') or '-')
                matricula   = self._safe(vals.get('matricula', '-') or '-')
                timestamp   = self._safe(str(item.get('timestamp', ''))[:16])
                
                self._cell(50, 6, f"Competencia: {competencia}", border='L')
                self._cell(60, 6, f"Matricula/Beneficio: {matricula}", border=0)
                self._cell(0,  6, f"Gerado em: {timestamp}", border='R', ln=True)

                # Rubrics Detail (Only if relevant)
                if vals['rubricas']:
                    self.set_fill_color(248, 248, 248)
                    self.set_font('Helvetica', 'B', 7)
                    self._cell(10, 5, "", border='L')
                    self._cell(40, 5, "RUBRICA", border=1, align='C', fill=True)
                    self._cell(50, 5, "VALOR DECLARADO", border=1, align='C', fill=True)
                    self._cell(0,  5, "", border='R', ln=True)
                    
                    self.set_font('Helvetica', '', 7)
                    for r in vals['rubricas']:
                        self._cell(10, 5, "", border='L')
                        self._cell(40, 5, r['cod'], border=1, align='C')
                        self._cell(50, 5, self._br(r['vr']), border=1, align='R')
                        self._cell(0,  5, "", border='R', ln=True)

                # Card Footer - Status and Recibo
                self.set_fill_color(240, 245, 250)
                self.set_font('Helvetica', 'B', 8)
                
                status = self._safe(item.get('status', '-'))
                recibo = self._safe(item.get('nr_recibo', '') or vals.get('nrRecBackup', '') or '-')
                r, g, b = self._status_color(status)
                
                self._cell(60, 8, f"  STATUS: ", border='LB', fill=True)
                curr_x = self.get_x() - 44
                curr_y = self.get_y()
                self.set_text_color(r, g, b)
                self.set_xy(curr_x, curr_y)
                self.cell(42, 8, status[:25])
                self.set_text_color(0, 0, 0)
                self.set_xy(curr_x + 44, curr_y)

                self._cell(0, 8, f"RECIBO: {recibo[:60]}", border='RB', fill=True, ln=True)
                self.ln(3)

        self.output(output_path)
        return output_path

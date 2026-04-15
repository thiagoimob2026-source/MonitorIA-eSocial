import customtkinter as ctk
from PIL import Image
import os
import json
import csv
import threading
import time
import re
import uuid
from tkinter import filedialog, messagebox
from esocial_native import ESocialNativeSender
from xml_validator import XMLValidator
from event_templates import (
    generate_event_xml, parse_esocial_xml, generate_xml_from_metadata,
    generate_s1000_xml  # Mantido: S-1000 não tem layout JSON ainda
)
from database import ESocialDatabase
import tkinter.ttk as ttk
from tkinter import messagebox
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import tempfile
import subprocess
import uuid

# Configure appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class LayoutEngine:
    """Core engine to manage eSocial layouts from JSON files."""
    def __init__(self, layouts_dir="layouts"):
        self.layouts_dir = layouts_dir
        self.layouts = {}
        self.load_all_layouts()

    def load_all_layouts(self):
        if not os.path.exists(self.layouts_dir):
            return
        for file in os.listdir(self.layouts_dir):
            if file.endswith(".json"):
                evt_type = file.replace(".json", "")
                try:
                    with open(os.path.join(self.layouts_dir, file), "r", encoding="utf-8") as f:
                        self.layouts[evt_type] = json.load(f)
                except Exception as e:
                    print(f"Erro ao carregar layout {file}: {e}")

    def get_layout(self, evt_type):
        return self.layouts.get(evt_type)

    def build_form(self, parent, evt_type, entries_dict):
        """Dynamically builds a grid of fields from the layout JSON."""
        layout = self.get_layout(evt_type)
        if not layout:
            return None
        
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Grid config (2 columns)
        container.columnconfigure((0, 1), weight=1)
        
        row_offset = 0
        for section in layout.get("sections", []):
            # Section Header
            s_frame = ctk.CTkFrame(container, fg_color="#2E4053")
            s_frame.grid(row=row_offset, column=0, columnspan=2, sticky="ew", pady=(10, 5))
            ctk.CTkLabel(s_frame, text=section["name"], font=ctk.CTkFont(weight="bold")).pack(pady=2)
            row_offset += 1
            
            for i, field in enumerate(section.get("fields", [])):
                row = row_offset + (i // 2)
                col = i % 2
                
                f_frame = ctk.CTkFrame(container, fg_color="transparent")
                f_frame.grid(row=row, column=col, padx=10, pady=3, sticky="ew")
                
                # Label with color coding based on requirement
                l_color = "#E67E22" if field.get("req") == "M" else "#B2BABB"
                l_text = f"{field['label']} *" if field.get("req") == "M" else field['label']
                l = ctk.CTkLabel(f_frame, text=l_text, width=130, anchor="w", text_color=l_color)
                l.pack(side="left")
                
                # Field Widget
                if field.get("type") == "options":
                    widget = ctk.CTkOptionMenu(f_frame, values=field.get("values", []), width=150)
                else:
                    widget = ctk.CTkEntry(f_frame, placeholder_text=field.get("placeholder", ""))
                
                if field.get("default"):
                    if isinstance(widget, ctk.CTkEntry):
                        widget.insert(0, str(field["default"]))
                    elif isinstance(widget, ctk.CTkOptionMenu):
                        widget.set(field["default"])
                
                widget.pack(side="right", fill="x", expand=True)
                entries_dict[field["tag"]] = widget
                
            row_offset += (len(section.get("fields", [])) + 1) // 2

        return container

class RubricGrid(ctk.CTkFrame):
    """A dynamic grid component to manage eSocial rubrics."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.rows = []
        self._setup_headers()
        self.add_row() # Start with one empty row

    def _setup_headers(self):
        h_frame = ctk.CTkFrame(self, fg_color="transparent")
        h_frame.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(h_frame, text="Cód. Rubrica", width=120, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(h_frame, text="Tabela", width=100, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkLabel(h_frame, text="Valor (R$)", width=100, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5)
        ctk.CTkButton(h_frame, text="+ Adicionar", width=100, command=self.add_row, fg_color="#2E86C1").pack(side="right", padx=5)

    def add_row(self, code="", amount="0.00", table="contindi"):
        row_f = ctk.CTkFrame(self, fg_color="transparent")
        row_f.pack(fill="x", padx=5, pady=1)
        
        e_code = ctk.CTkEntry(row_f, width=120, placeholder_text="Ex: 1000")
        e_code.insert(0, code)
        e_code.pack(side="left", padx=5)
        
        e_table = ctk.CTkEntry(row_f, width=100, placeholder_text="Tabela")
        e_table.insert(0, table)
        e_table.pack(side="left", padx=5)
        
        e_val = ctk.CTkEntry(row_f, width=100, placeholder_text="0.00")
        e_val.insert(0, amount)
        e_val.pack(side="left", padx=5)
        
        btn_del = ctk.CTkButton(row_f, text="X", width=30, fg_color="#C0392B", hover_color="#943126", command=lambda f=row_f: self.remove_row(f))
        btn_del.pack(side="right", padx=5)
        
        self.rows.append({'frame': row_f, 'code': e_code, 'val': e_val, 'table': e_table})

    def remove_row(self, frame):
        for i, r in enumerate(self.rows):
            if r['frame'] == frame:
                r['frame'].destroy()
                self.rows.pop(i)
                break
                
    def get_data(self):
        data = []
        for r in self.rows:
            c = r['code'].get().strip()
            v = r['val'].get().strip().replace(',', '.')
            t = r['table'].get().strip() or "contindi"
            if c:
                data.append({
                    'codRubr': c, 
                    'vrRubr': v, 
                    'ideTabRubr': t,
                    'indApurIR': '0' # Default para período de apuração mensal
                })
        return data

    def clear(self):
        for r in self.rows:
            r['frame'].destroy()
        self.rows = []

class DmDevItem(ctk.CTkFrame):
    """Container for a single ideDmDev block with its own RubricGrid."""
    def __init__(self, master, ide_dm_dev="001", on_delete=None, **kwargs):
        super().__init__(master, fg_color="transparent", border_width=1, border_color="gray", **kwargs)
        self.on_delete = on_delete
        
        header = ctk.CTkFrame(self, fg_color="#2E4053", height=30)
        header.pack(fill="x", padx=2, pady=2)
        
        ctk.CTkLabel(header, text="ID Demonstrativo:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10)
        self.entry_id = ctk.CTkEntry(header, width=80)
        self.entry_id.insert(0, ide_dm_dev)
        self.entry_id.pack(side="left", padx=5)
        
        if on_delete:
            ctk.CTkButton(header, text="Remover Bloco", width=100, fg_color="#922B21", command=on_delete).pack(side="right", padx=5)
            
        self.rubric_grid = RubricGrid(self)
        self.rubric_grid.pack(fill="x", padx=10, pady=10)
        
    def get_data(self):
        return {
            'ideDmDev': self.entry_id.get().strip(),
            'rubrics': self.rubric_grid.get_data()
        }

class DmDevManager(ctk.CTkFrame):
    """Manages multiple DmDevItem blocks."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.items = []
        
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="x")
        
        self.btn_add = ctk.CTkButton(self, text="+ Adicionar Novo Demonstrativo", command=self.add_dm, fg_color="#28B463")
        self.btn_add.pack(pady=10)
        
        self.add_dm("001") # Start with default

    def add_dm(self, ide=""):
        if not ide:
            # Suggest next ID
            existing_ids = [i.entry_id.get() for i in self.items]
            for n in range(1, 100):
                candidate = str(n).zfill(3)
                if candidate not in existing_ids:
                    ide = candidate
                    break

        item = DmDevItem(self.content_frame, ide_dm_dev=ide, on_delete=lambda: self.remove_dm(item))
        item.pack(fill="x", pady=5)
        self.items.append(item)
        return item

    def remove_dm(self, item):
        if len(self.items) <= 1:
            messagebox.showwarning("Aviso", "O evento deve conter pelo menos um demonstrativo.")
            return
        item.destroy()
        self.items.remove(item)

    def get_data(self):
        return [i.get_data() for i in self.items]

    def clear(self):
        for i in self.items:
            i.destroy()
        self.items = []

class InfoPgtoItem(ctk.CTkFrame):
    def __init__(self, master, on_delete, **kwargs):
        super().__init__(master, border_width=1, border_color="gray", corner_radius=5, **kwargs)
        
        # Row 1: Dados Principais e Botão Remover
        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(row1, text="Data Pgto:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(5,2))
        self.dtPgto = ctk.CTkEntry(row1, width=85, placeholder_text="DDMMAAAA")
        self.dtPgto.pack(side="left", padx=2)
        
        ctk.CTkLabel(row1, text="Período Ref:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(10,2))
        self.perRef = ctk.CTkEntry(row1, width=75, placeholder_text="AAAA-MM")
        self.perRef.pack(side="left", padx=2)
        
        ctk.CTkLabel(row1, text="Tp Pgto:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(10,2))
        self.tpPgto = ctk.CTkEntry(row1, width=40)
        self.tpPgto.insert(0, "1")
        self.tpPgto.pack(side="left", padx=2)

        ctk.CTkLabel(row1, text="Vr Líquido:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(10,2))
        self.vrLiq = ctk.CTkEntry(row1, width=80)
        self.vrLiq.insert(0, "0.00")
        self.vrLiq.pack(side="left", padx=2)
        
        ctk.CTkLabel(row1, text="IDs Dem:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(10,2))
        self.ideDmDevs = ctk.CTkEntry(row1, width=80, placeholder_text="001, 002...")
        self.ideDmDevs.insert(0, "001")
        self.ideDmDevs.pack(side="left", padx=2)
        
        btn_del = ctk.CTkButton(row1, text="X", width=30, fg_color="#C0392B", command=on_delete)
        btn_del.pack(side="right", padx=5)

        # Row 2: Complementares DIRF
        row2 = ctk.CTkFrame(self, fg_color="#2C3E50", corner_radius=5)
        row2.pack(fill="x", padx=10, pady=(0, 5))
        
        ctk.CTkLabel(row2, text="DIRF (Opcional) |", font=ctk.CTkFont(size=11, weight="bold"), text_color="#F1C40F").pack(side="left", padx=(5,5))
        
        ctk.CTkLabel(row2, text="CR:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        self.cr = ctk.CTkEntry(row2, width=60, height=24, placeholder_text="056107")
        self.cr.pack(side="left", padx=2)
        
        ctk.CTkLabel(row2, text="VR IR:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        self.vrIRRF = ctk.CTkEntry(row2, width=60, height=24, placeholder_text="0.00")
        self.vrIRRF.pack(side="left", padx=2)
        
        ctk.CTkLabel(row2, text="CPF Dep:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10,2))
        self.cpfDep = ctk.CTkEntry(row2, width=100, height=24)
        self.cpfDep.pack(side="left", padx=2)

        ctk.CTkLabel(row2, text="Ded Dep:", font=ctk.CTkFont(size=11)).pack(side="left", padx=2)
        self.vlrDedDep = ctk.CTkEntry(row2, width=60, height=24, placeholder_text="0.00")
        self.vlrDedDep.pack(side="left", padx=2)

    def get_data(self):
        dem_list = [x.strip() for x in self.ideDmDevs.get().split(",") if x.strip()]
        if not dem_list: dem_list = ["001"]
        return {
            'dtPgto': self.dtPgto.get().strip(),
            'tpPgto': self.tpPgto.get().strip(),
            'perRef': self.perRef.get().strip(),
            'vrLiq': self.vrLiq.get().strip(),
            'demonstrativos': [{'ideDmDev': dem} for dem in dem_list],
            'cr': self.cr.get().strip(),
            'vrIRRF': self.vrIRRF.get().strip(),
            'cpfDep': self.cpfDep.get().strip(),
            'vlrDedDep': self.vlrDedDep.get().strip()
        }

class InfoPgtoManager(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.items = []
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(fill="x")
        self.btn_add = ctk.CTkButton(self, text="+ Adicionar Pagamento", command=self.add_pgto, fg_color="#F39C12")
        self.btn_add.pack(pady=10)
        self.add_pgto()

    def add_pgto(self):
        item = InfoPgtoItem(self.content_frame, on_delete=lambda: self.remove_pgto(item))
        item.pack(fill="x", pady=5)
        self.items.append(item)
        return item

    def remove_pgto(self, item):
        if len(self.items) <= 1:
            messagebox.showwarning("Aviso", "Deve conter pelo menos um pagamento.")
            return
        item.destroy()
        self.items.remove(item)

    def get_data(self):
        return [i.get_data() for i in self.items]

    def clear(self):
        for i in self.items:
            i.destroy()
        self.items = []

# --- Componentes Reutilizáveis ---

class SideListPanel(ctk.CTkFrame):
    """Dynamic side panel that toggles between DB History and CSV Review Queue."""
    def __init__(self, parent, app, evt_type=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self.evt_type = evt_type
        self.mode = "HISTORY" # Can be "HISTORY" or "QUEUE"
        
        # Header with Toggle
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=10, pady=5)
        
        self.title_lbl = ctk.CTkLabel(self.header, text=f"Histórico ({evt_type})", font=ctk.CTkFont(weight="bold"))
        self.title_lbl.pack(side="left")
        
        self.toggle_btn = ctk.CTkButton(self.header, text="Alternar Modo", width=100, font=ctk.CTkFont(size=10), 
                                       command=self.toggle_mode, fg_color="#34495E")
        self.toggle_btn.pack(side="right")
        
        # Toolbar
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.pack(fill="x", padx=5, pady=2)
        
        self.btn_refresh = ctk.CTkButton(self.toolbar, text="🔄", width=30, command=self.refresh, fg_color="#27AE60")
        self.btn_refresh.pack(side="left", padx=2)
        
        self.btn_view = ctk.CTkButton(self.toolbar, text="🔎 Ver", width=60, command=self.view_details, fg_color="#F39C12")
        self.btn_view.pack(side="left", padx=2)
        
        self.btn_load = ctk.CTkButton(self.toolbar, text="📝 Conferir", width=80, command=self.load, fg_color="#2E86C1")
        self.btn_load.pack(side="left", padx=2)
        
        self.btn_action = ctk.CTkButton(self.toolbar, text="🚀 Enviar", width=70, command=self.send, fg_color="green")
        self.btn_action.pack(side="left", padx=2)
        
        self.btn_all = ctk.CTkButton(self.toolbar, text="💾 Salvar Tudo", width=90, command=self.save_all_queue, fg_color="#1D8348")
        # Initially hidden, will show/hide in refresh()
        
        self.btn_del = ctk.CTkButton(self.toolbar, text="🗑️", width=30, command=self.delete, fg_color="#C0392B")
        self.btn_del.pack(side="left", padx=2)
        
        # Treeview
        tree_frame = ctk.CTkFrame(self)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        columns = ("evt_id", "type", "cpf", "status", "protocol", "recibo", "timestamp")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        
        widths = {
            "evt_id": 140, "type": 60, "cpf": 100, "status": 80, 
            "protocol": 120, "recibo": 120, "timestamp": 120
        }
        for col in columns:
            title = "RECIBO" if col == "recibo" else "PROT." if col == "protocol" else col.upper()
            self.tree.heading(col, text=title)
            self.tree.column(col, width=widths[col], anchor="center")
            
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.refresh()

    def toggle_mode(self):
        self.mode = "QUEUE" if self.mode == "HISTORY" else "HISTORY"
        self.refresh()

    def set_mode(self, mode):
        self.mode = mode
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if self.mode == "HISTORY":
            self.title_lbl.configure(text=f"Histórico ({self.evt_type})", text_color="white")
            self.btn_load.configure(text="📝 Carreg")
            self.btn_action.pack(side="left", padx=2)
            self.btn_action.configure(text="🚀 Enviar", state="normal")
            self.btn_all.pack_forget()
            self._refresh_history()
        else:
            count = len(self.app.batch_queues.get(self.evt_type, []))
            self.title_lbl.configure(text=f"Fila Conferência ({count})", text_color="#10B981")
            self.btn_load.configure(text="📝 Conferir")
            self.btn_action.pack_forget() # Hide "Enviar" in review mode
            self.btn_all.pack(side="left", padx=2)
            self._refresh_queue()

    def save_all_queue(self):
        queue = self.app.batch_queues.get(self.evt_type, [])
        if not queue:
            messagebox.showinfo("Fila Vazia", "Não há itens na fila para salvar.")
            return
        
        if messagebox.askyesno("Confirmar", f"Deseja salvar os {len(queue)} itens da fila diretamente no histórico sem conferência individual?"):
            saved = 0
            errors = 0
            for item_data in list(queue):
                try:
                    self.app.save_queue_item_to_db(self.evt_type, item_data)
                    saved += 1
                except Exception as e:
                    errors += 1
                    self.app.log(f"  ERRO ao salvar CPF {item_data.get('cpfTrab', '?')}: {e}")
            
            queue.clear()
            # Switch panel to HISTORY mode so saved items are visible here
            self.mode = "HISTORY"
            self.refresh()
            # Also update the main History tab
            self.app.refresh_history()
            self.app.log(f"Lote salvo: {saved} OK, {errors} erros ({self.evt_type}).")
            if errors == 0:
                messagebox.showinfo("Sucesso", f"{saved} evento(s) salvos no histórico com sucesso!")
            else:
                messagebox.showwarning("Salvo com erros", f"{saved} salvos, {errors} com erro.\nVerifique o log para detalhes.")

    def _refresh_history(self):
        self.tree.tag_configure("success", foreground="#10B981")
        self.tree.tag_configure("error", foreground="#EF4444")
        self.tree.tag_configure("pending", foreground="#F59E0B")
        self.tree.tag_configure("default", foreground="#F8FAFC")
        
        history = self.app.db.get_history(evt_type=self.evt_type)
        for h in history:
            status = str(h["status"])
            tag = "success" if "Aceito" in status else "error" if any(x in status for x in ["Erro", "Rejeitado"]) else "pending" if "PENDENTE" in status else "default"
            self.tree.insert("", "end", values=(h["evt_id"], h["type"], h["cpf"], h["status"], h["protocol"] or "-", h["nr_recibo"] or "-", h["timestamp"]), tags=(tag,))

    def _refresh_queue(self):
        self.tree.tag_configure("queue", foreground="#A9CCE3")
        queue = self.app.batch_queues.get(self.evt_type, [])
        for idx, item in enumerate(queue):
            # Queue items use idx as 'evt_id' for selection
            self.tree.insert("", "end", values=(f"Linha {idx+1}", self.evt_type, item['cpfTrab'], "PENDENTE", "-", "-", "CSV Import"), tags=("queue",))

    def view_details(self):
        if self.mode == "QUEUE": return
        selected = self.tree.selection()
        if not selected: return
        old_tree = self.app.tree; self.app.tree = self.tree; self.app.view_totalizer(); self.app.tree = old_tree

    def load(self):
        selected = self.tree.selection()
        if not selected: return
        
        if self.mode == "HISTORY":
            old_tree = self.app.tree; self.app.tree = self.tree; self.app.load_for_edit(); self.app.tree = old_tree
        else:
            # Load from Memory Queue
            idx_str = self.tree.item(selected[0])["values"][0]
            try:
                idx = int(idx_str.replace("Linha ", "")) - 1
                queue = self.app.batch_queues.get(self.evt_type, [])
                if 0 <= idx < len(queue):
                    self.app.current_review_index = idx
                    self.app.populate_form_from_data(self.evt_type, queue[idx])
                    self.app.log(f"Carregado item {idx+1} da fila para conferência.")
            except: pass

    def send(self):
        if self.mode == "QUEUE": return
        selected = self.tree.selection()
        if not selected: return
        old_tree = self.app.tree; self.app.tree = self.tree; self.app.send_selected_event(); self.app.tree = old_tree

    def delete(self):
        selected = self.tree.selection()
        if not selected: return
        if self.mode == "HISTORY":
            old_tree = self.app.tree; self.app.tree = self.tree; self.app.delete_selected(); self.app.tree = old_tree
        else:
            idx_str = self.tree.item(selected[0])["values"][0]
            try:
                idx = int(idx_str.replace("Linha ", "")) - 1
                self.app.batch_queues[self.evt_type].pop(idx)
                self.refresh()
            except: pass

class ESocialApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("IA_eSocial Monitor (Módulo Nativo)")
        self.geometry("1100x700")

        # Native eSocial Sender
        self.native_sender = ESocialNativeSender(console_log_callback=self.log)
        self.config_data = self.load_config()
        self.db = ESocialDatabase()
        self.batch_queues = {"S-1200": [], "S-1202": [], "S-1207": [], "S-1210": []}
        self.current_review_index = None
        self.validator = XMLValidator()
        self.layouts = LayoutEngine()
        
        # Load Configuration First
        self.load_config()

        # Appearance Configuration
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")
        
        # Configure ttk style for Dark Mode Treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        background="#1A1C23", 
                        foreground="#F8FAFC", 
                        fieldbackground="#1A1C23", 
                        rowheight=25,
                        font=("Arial", 9))
        style.configure("Treeview.Heading", 
                        background="#0F172A", 
                        foreground="white", 
                        font=("Arial", 10, "bold"))
        style.map("Treeview", background=[('selected', '#10B981')])
        
        # Grid configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="e-Social App", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.s1200_button = ctk.CTkButton(self.sidebar_frame, text=" 📊 RGPS (S-1200)", anchor="w", command=self.show_s1200, height=35)
        self.s1200_button.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.s1202_button = ctk.CTkButton(self.sidebar_frame, text=" 🏢 Ativos (S-1202)", anchor="w", command=self.show_s1202, height=35)
        self.s1202_button.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.s1207_button = ctk.CTkButton(self.sidebar_frame, text=" 💰 Benefícios (S-1207)", anchor="w", command=self.show_s1207, height=35)
        self.s1207_button.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        self.s1210_button = ctk.CTkButton(self.sidebar_frame, text=" 💸 Pagamentos (S-1210)", anchor="w", command=self.show_s1210, height=35)
        self.s1210_button.grid(row=4, column=0, padx=20, pady=5, sticky="ew")

        self.history_button = ctk.CTkButton(self.sidebar_frame, text=" 📂 Histórico / Recibos", anchor="w", command=self.show_history, fg_color="#2E86C1", height=40)
        self.history_button.grid(row=5, column=0, padx=20, pady=10, sticky="ew")

        self.s1000_btn = ctk.CTkButton(self.sidebar_frame, text=" 🏛️ Empregador (S-1000)", anchor="w", command=self.show_s1000, height=35)
        self.s1000_btn.grid(row=6, column=0, padx=20, pady=5, sticky="ew")

        self.s3000_btn = ctk.CTkButton(self.sidebar_frame, text=" ❌ Exclusão (S-3000)", anchor="w", command=self.show_s3000, height=35)
        self.s3000_btn.grid(row=7, column=0, padx=20, pady=5, sticky="ew")

        self.xml_btn = ctk.CTkButton(self.sidebar_frame, text=" 🛠️ Acertos XML (Beta)", anchor="w", command=self.show_xml_adj, height=35)
        self.xml_btn.grid(row=8, column=0, padx=20, pady=5, sticky="ew")

        self.reports_btn = ctk.CTkButton(self.sidebar_frame, text=" 📜 Relatórios PDF", anchor="w", command=self.show_reports, fg_color="#27AE60", height=35)
        self.reports_btn.grid(row=9, column=0, padx=20, pady=5, sticky="ew")

        self.config_button = ctk.CTkButton(self.sidebar_frame, text=" ⚙️ Configurações", anchor="w", command=self.show_config, height=35)
        self.config_button.grid(row=10, column=0, padx=20, pady=5, sticky="ew")

        self.manual_button = ctk.CTkButton(self.sidebar_frame, text=" 📖 Manual do Sistema", anchor="w", command=self.show_manual, fg_color="#F39C12", hover_color="#D68910", height=35)
        self.manual_button.grid(row=11, column=0, padx=20, pady=10, sticky="ew")

        self.env_label = ctk.CTkLabel(self.sidebar_frame, text=f"Ambiente: {self.get_env_name()}", font=ctk.CTkFont(size=12, weight="bold"), text_color="orange")
        self.env_label.grid(row=12, column=0, padx=20, pady=5)

        self.appearance_label = ctk.CTkLabel(self.sidebar_frame, text="Tema:", anchor="w")
        self.appearance_label.grid(row=13, column=0, padx=20, pady=(10, 0))
        self.appearance_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Dark", "Light"], command=self.change_appearance)
        self.appearance_menu.grid(row=14, column=0, padx=20, pady=(10, 20))

        # Main Content Area
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Pages
        self.tabview.add("Home")
        self.tabview.add("S-1000")
        self.tabview.add("S-1200")
        self.tabview.add("S-1202")
        self.tabview.add("S-1207")
        self.tabview.add("S-1210")
        self.tabview.add("S-3000")
        self.tabview.add("Histórico")
        self.tabview.add("Ajuste XML")
        self.tabview.add("Relatórios")
        self.tabview.add("Config")
        self.tabview.add("Manual")
        self.step_frames = {}
        self.current_step = 1
        self.correction_data = {
            "xml_path": None,
            "parsed_data": None,
            "event_type": None,
            "original_receipt": None,
            "s3000_sent": False
        }
        
        self.setup_home_tab()
        self.setup_s1000_tab()
        self.setup_s1200_tab()
        self.setup_s1202_tab()
        self.setup_s1207_tab()
        self.setup_s1210_tab()
        self.setup_s3000_tab()
        self.setup_history_tab()
        self.setup_xml_adj_tab()
        self.setup_reports_tab()
        self.setup_config_tab()
        self.setup_manual_tab()
        
        self.xml_data = {"xml1": None, "xml2": None, "rubrics": [], "cpf": "", "perApur": "2026-02"}

        self.show_home()
        self.refresh_dashboard()

        # Console area
        self.console_frame = ctk.CTkFrame(self, height=150)
        self.console_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=20, pady=(0, 20))
        self.console_frame.grid_columnconfigure(0, weight=1)
        self.console_frame.grid_rowconfigure(1, weight=1)

        self.console_label = ctk.CTkLabel(self.console_frame, text="Logs de Comunicação eSocial Gov (Nativo)", font=ctk.CTkFont(size=12, weight="bold"))
        self.console_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        self.console_text = ctk.CTkTextbox(self.console_frame, height=100)
        self.console_text.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

    def load_config(self):
        # Local persistente em AppData
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.base_dir = os.path.join(appdata, "IA_eSocial")
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
        self.config_file = os.path.join(self.base_dir, "config.json")
        
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                self.config_data = json.load(f)
                # Defaults for new fields
                defaults = {
                    "tpInsc": "1", 
                    "smtp_host": "smtp.gmail.com", 
                    "smtp_port": 587,
                    "sender_email": "",
                    "email_pass": "",
                    "target_email": "",
                    "pasta_xml": ""
                }
                for k, v in defaults.items():
                    if k not in self.config_data:
                        self.config_data[k] = v
        else:
            self.config_data = {
                "host": "127.0.0.1", "port": 3434, "nrInsc": "", 
                "tpAmb": "2", "tpInsc": "1",
                "smtp_host": "smtp.gmail.com", "smtp_port": 587,
                "sender_email": "", "email_pass": "", "target_email": "",
                "pasta_xml": ""
            }
            self.save_config()
        
        self.native_sender.host = self.config_data.get("host", "127.0.0.1")

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(self.config_data, f, indent=4)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.console_text.insert("end", f"[{timestamp}] {message}\n")
        self.console_text.see("end")

    def change_appearance(self, mode):
        ctk.set_appearance_mode(mode)

    def show_home(self):
        self.tabview.set("Home")

    def show_s1000(self):
        self.tabview.set("S-1000")

    def show_s1200(self):
        self.tabview.set("S-1200")

    def show_s1202(self):
        self.tabview.set("S-1202")

    def show_s1207(self):
        self.tabview.set("S-1207")

    def show_s1210(self):
        self.tabview.set("S-1210")

    def show_config(self):
        self.tabview.set("Config")

    def show_history(self):
        self.refresh_history()
        self.tabview.set("Histórico")

    def show_xml_adj(self):
        self.tabview.set("Ajuste XML")

    def show_s3000(self):
        self.tabview.set("S-3000")

    def show_manual(self):
        self.tabview.set("Manual")

    # --- Tab Setup ---

    def setup_home_tab(self):
        tab = self.tabview.tab("Home")
        tab.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Header
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=20)
        
        ctk.CTkLabel(header, text="📊 Painel de Controle IA_eSocial", font=ctk.CTkFont(size=28, weight="bold")).pack(side="left")
        
        self.status_label_top = ctk.CTkLabel(header, text="Status A3: Pendente", font=ctk.CTkFont(size=14), text_color="orange")
        self.status_label_top.pack(side="right", padx=10)
        
        # --- Stats Cards ---
        self.stats_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.stats_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=20, pady=10)
        self.stats_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Success Card
        self.card_success = ctk.CTkFrame(self.stats_frame, height=120, fg_color="#1E293B", border_width=2, border_color="#10B981")
        self.card_success.grid(row=0, column=0, padx=10, sticky="ew")
        ctk.CTkLabel(self.card_success, text="Sucessos", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))
        self.lbl_stat_success = ctk.CTkLabel(self.card_success, text="0", font=ctk.CTkFont(size=32, weight="bold"), text_color="#10B981")
        self.lbl_stat_success.pack(pady=5)
        
        # Fail Card
        self.card_fail = ctk.CTkFrame(self.stats_frame, height=120, fg_color="#1E293B", border_width=2, border_color="#EF4444")
        self.card_fail.grid(row=0, column=1, padx=10, sticky="ew")
        ctk.CTkLabel(self.card_fail, text="Erros / Rejeições", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))
        self.lbl_stat_fail = ctk.CTkLabel(self.card_fail, text="0", font=ctk.CTkFont(size=32, weight="bold"), text_color="#EF4444")
        self.lbl_stat_fail.pack(pady=5)
        
        # Pending Card
        self.card_pending = ctk.CTkFrame(self.stats_frame, height=120, fg_color="#1E293B", border_width=2, border_color="#F59E0B")
        self.card_pending.grid(row=0, column=2, padx=10, sticky="ew")
        ctk.CTkLabel(self.card_pending, text="Pendentes", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 5))
        self.lbl_stat_pending = ctk.CTkLabel(self.card_pending, text="0", font=ctk.CTkFont(size=32, weight="bold"), text_color="#F59E0B")
        self.lbl_stat_pending.pack(pady=5)
        
        # --- Quick Actions & Tools ---
        bottom_frame = ctk.CTkFrame(tab, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=20, pady=20)
        bottom_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Connection Card
        self.conn_card = ctk.CTkFrame(bottom_frame)
        self.conn_card.grid(row=0, column=0, padx=10, sticky="nsew")
        ctk.CTkLabel(self.conn_card, text="🔌 Certificado Digital", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        ctk.CTkButton(self.conn_card, text="Verificar A3", command=self.test_connection, width=150).pack(pady=10)
        
        # Shortcut Card
        self.shortcut_card = ctk.CTkFrame(bottom_frame)
        self.shortcut_card.grid(row=0, column=1, padx=10, sticky="nsew")
        ctk.CTkLabel(self.shortcut_card, text="🚀 Acesso Rápido", font=ctk.CTkFont(weight="bold")).pack(pady=10)
        
        btn_grid = ctk.CTkFrame(self.shortcut_card, fg_color="transparent")
        btn_grid.pack(pady=5)
        
        ctk.CTkButton(btn_grid, text="Novo S-1200", command=self.show_s1200, fg_color="#10B981", width=120).pack(side="left", padx=5)
        ctk.CTkButton(btn_grid, text="📧 Enviar Resumo", command=self.send_email_report, fg_color="#2E86C1", width=120).pack(side="left", padx=5)

        # Consultation Section
        self.consult_frame = ctk.CTkFrame(tab)
        self.consult_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=20, pady=10)
        ctk.CTkLabel(self.consult_frame, text="🔎 Consulta Síncrona de Lote", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=20, pady=20)
        
        self.protocol_entry = ctk.CTkEntry(self.consult_frame, placeholder_text="Protocolo de envio...", width=300)
        self.protocol_entry.pack(side="left", padx=10)
        
        ctk.CTkButton(self.consult_frame, text="Consultar no Governo", command=self.process_consult_lote).pack(side="left", padx=10)

    def refresh_dashboard(self):
        """Updates the home stats with data from SQLite."""
        try:
            stats = self.db.get_dashboard_stats()
            self.lbl_stat_success.configure(text=str(stats["success"]))
            self.lbl_stat_fail.configure(text=str(stats["fail"]))
            self.lbl_stat_pending.configure(text=str(stats["pending"]))
        except Exception as e:
            self.log(f"Falha ao atualizar dashboard: {e}")

    def test_connection(self):
        self.log("Verificando Certificado A3 no Windows...")
        cnpj = self.config_data.get("nrInsc", "")
        # Use a small PS script to list certs
        ps_cmd = f'Get-Item Cert:\\CurrentUser\\My\\* | Where-Object {{ $_.Subject -like "*{cnpj}*" -or $_.FriendlyName -like "*{cnpj}*" }} | Select-Object Subject, FriendlyName, NotAfter | ConvertTo-Json'
        
        try:
            result = subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, text=True)
            if result.stdout.strip():
                cert_info = json.loads(result.stdout)
                if isinstance(cert_info, list): cert_info = cert_info[0]
                self.log(f"Certificado Encontrado: {cert_info.get('Subject')}")
                # Update UI Status Label
                self.status_label.configure(text="Status A3: CERTIFICADO OK", text_color="green")
            else:
                self.log(f"ERRO: Certificado para CNPJ {cnpj} não encontrado no repositório 'Pessoal'.")
                self.status_label.configure(text="Status A3: NÃO ENCONTRADO", text_color="red")
        except Exception as e:
            self.log(f"Erro ao testar certificado: {e}")
            self.status_label.configure(text="Status A3: ERRO", text_color="red")

    def setup_s1200_tab(self):
        tab = self.tabview.tab("S-1200")
        
        # Split layout: Form (Left) | History (Right)
        main_container = ctk.CTkFrame(tab, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        
        left_col = ctk.CTkFrame(main_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        right_col = ctk.CTkFrame(main_container, width=450)
        right_col.pack(side="right", fill="both", padx=(5, 0))
        right_col.pack_propagate(False)
        
        page = ctk.CTkScrollableFrame(left_col, fg_color="transparent")
        page.pack(fill="both", expand=True)
        
        self.s1200_qhistory = SideListPanel(right_col, self, evt_type="S-1200")
        self.s1200_qhistory.pack(fill="both", expand=True)

        self.s1200_entries = {}
        
        # Header with Import Button
        h_frame = ctk.CTkFrame(page, fg_color="transparent")
        h_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(h_frame, text="S-1200 - Remuneração RGPS", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(h_frame, text="Importar XML para Retificar", command=lambda: self.import_rect_xml("S-1200"), fg_color="#F39C12").pack(side="right", padx=5)
        ctk.CTkButton(h_frame, text="Excluir via XML (S-3000)", command=lambda: self.import_exclude_xml("S-1200"), fg_color="#C0392B").pack(side="right")

        # Rectification Mode
        self.s1200_retif_frame = ctk.CTkFrame(page, fg_color="#34495E")
        self.s1200_retif_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(self.s1200_retif_frame, text="Tipo de Envio:").pack(side="left", padx=10)
        self.s1200_ind_retif = ctk.CTkOptionMenu(self.s1200_retif_frame, values=["1 - Original", "2 - Retificadora"], width=150)
        self.s1200_ind_retif.pack(side="left", padx=5)
        
        ctk.CTkLabel(self.s1200_retif_frame, text="Recibo Original:").pack(side="left", padx=10)
        self.s1200_nr_rec = ctk.CTkEntry(self.s1200_retif_frame, placeholder_text="Obrigatório se Retificadora", width=250)
        self.s1200_nr_rec.pack(side="left", padx=5, fill="x", expand=True)
        
        help_retif = ctk.CTkLabel(page, text="💡 Se usar 'Retificadora', informe o número do recibo do evento que deseja corrigir.", font=ctk.CTkFont(size=11), text_color="gray")
        help_retif.pack(padx=20, pady=(0, 5), anchor="w")

        # Form Fields (Identity & Period)
        self.form_container = self.layouts.build_form(page, "S-1200", self.s1200_entries)
            
        help_fields = ctk.CTkLabel(page, text="📝 Matrícula: Obrigatória para celetistas. Se vazia, preencha Nome/Nasc (Obrigatórios p/ categorias como 701).", font=ctk.CTkFont(size=11), text_color="#A9CCE3")
        help_fields.pack(padx=20, pady=5, anchor="w")

        ctk.CTkLabel(page, text="Gerenciador de Demonstrativos (ideDmDev)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.s1200_dm_manager = DmDevManager(page)
        self.s1200_dm_manager.pack(fill="x", padx=20, pady=5)

        self.send_btn = ctk.CTkButton(page, text="Salvar S-1200 (RGPS) na Fila", command=self.process_s1200, height=45, fg_color="#2E86C1")
        self.send_btn.pack(pady=20)

        # Separator for batch processing
        sep = ctk.CTkFrame(page, height=2, fg_color="gray")
        sep.pack(fill="x", padx=20, pady=20)

        label_batch = ctk.CTkLabel(page, text="Processamento em Lote (Planilha CSV)", font=ctk.CTkFont(size=16, weight="bold"))
        label_batch.pack(pady=5)

        batch_frame = ctk.CTkFrame(page, fg_color="transparent")
        batch_frame.pack(fill="x", padx=20, pady=5)
        
        self.gen_csv_btn = ctk.CTkButton(batch_frame, text="Gerar Planilha Modelo (CSV)", command=lambda: self.generate_csv_template("S-1200"), height=35)
        self.gen_csv_btn.pack(side="left", padx=10, fill="x", expand=True)

        self.import_csv_btn = ctk.CTkButton(batch_frame, text="Importar e Salvar em Lote (CSV)", command=self.process_s1200_batch, height=35)
        self.import_csv_btn.pack(side="right", padx=10, fill="x", expand=True)

    def setup_s1202_tab(self):
        tab = self.tabview.tab("S-1202")
        
        # Split layout
        main_container = ctk.CTkFrame(tab, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        
        left_col = ctk.CTkFrame(main_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        right_col = ctk.CTkFrame(main_container, width=450)
        right_col.pack(side="right", fill="both", padx=(5, 0))
        right_col.pack_propagate(False)
        
        page = ctk.CTkScrollableFrame(left_col, fg_color="transparent")
        page.pack(fill="both", expand=True)
        
        self.s1202_qhistory = SideListPanel(right_col, self, evt_type="S-1202")
        self.s1202_qhistory.pack(fill="both", expand=True)
        
        # Header with Import
        h_frame = ctk.CTkFrame(page, fg_color="transparent")
        h_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(h_frame, text="S-1202 - Remuneração Servidor Ativo (RPPS)", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(h_frame, text="Importar XML para Retificar", command=lambda: self.import_rect_xml("S-1202"), fg_color="#F39C12").pack(side="right", padx=5)
        ctk.CTkButton(h_frame, text="Excluir via XML (S-3000)", command=lambda: self.import_exclude_xml("S-1202"), fg_color="#C0392B").pack(side="right")

        # Rectification Mode
        self.s1202_retif_frame = ctk.CTkFrame(page, fg_color="#34495E")
        self.s1202_retif_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(self.s1202_retif_frame, text="Tipo de Envio:").pack(side="left", padx=10)
        self.s1202_ind_retif = ctk.CTkOptionMenu(self.s1202_retif_frame, values=["1 - Original", "2 - Retificadora"], width=150)
        self.s1202_ind_retif.pack(side="left", padx=5)
        ctk.CTkLabel(self.s1202_retif_frame, text="Recibo Original:").pack(side="left", padx=10)
        self.s1202_nr_rec = ctk.CTkEntry(self.s1202_retif_frame, placeholder_text="Obrigatório se Retificadora", width=250)
        self.s1202_nr_rec.pack(side="left", padx=5, fill="x", expand=True)

        self.s1202_entries = {}
        self.s1202_form = self.layouts.build_form(page, "S-1202", self.s1202_entries)

        ctk.CTkLabel(page, text="Gerenciador de Demonstrativos (ideDmDev)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.s1202_dm_manager = DmDevManager(page)
        self.s1202_dm_manager.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(page, text="Salvar S-1202 (RPPS) na Fila", command=self.process_s1202, height=45, fg_color="#27AE60").pack(pady=20)

        # Separator for batch processing
        sep = ctk.CTkFrame(page, height=2, fg_color="gray")
        sep.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(page, text="Processamento em Lote (S-1202)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)

        batch_frame = ctk.CTkFrame(page, fg_color="transparent")
        batch_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(batch_frame, text="Gerar Planilha Modelo (CSV)", command=lambda: self.generate_csv_template("S-1202"), height=35).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(batch_frame, text="Importar CSV (S-1202)", command=self.process_s1202_batch, height=35).pack(side="right", padx=10, fill="x", expand=True)

    def setup_s1207_tab(self):
        tab = self.tabview.tab("S-1207")
        main_container = ctk.CTkFrame(tab, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        
        left_col = ctk.CTkFrame(main_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        right_col = ctk.CTkFrame(main_container, width=450)
        right_col.pack(side="right", fill="both", padx=(5, 0))
        right_col.pack_propagate(False)
        
        page = ctk.CTkScrollableFrame(left_col, fg_color="transparent")
        page.pack(fill="both", expand=True)
        
        self.s1207_qhistory = SideListPanel(right_col, self, evt_type="S-1207")
        self.s1207_qhistory.pack(fill="both", expand=True)

        ctk.CTkLabel(page, text="S-1207 - Benefícios Entes Federados", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        
        # Rectification Mode
        self.s1207_retif_frame = ctk.CTkFrame(page, fg_color="#34495E")
        self.s1207_retif_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(self.s1207_retif_frame, text="Tipo de Envio:").pack(side="left", padx=10)
        self.s1207_ind_retif = ctk.CTkOptionMenu(self.s1207_retif_frame, values=["1 - Original", "2 - Retificadora"], width=150)
        self.s1207_ind_retif.pack(side="left", padx=5)
        ctk.CTkLabel(self.s1207_retif_frame, text="Recibo Original:").pack(side="left", padx=10)
        self.s1207_nr_rec = ctk.CTkEntry(self.s1207_retif_frame, placeholder_text="Obrigatório se Retificadora", width=250)
        self.s1207_nr_rec.pack(side="left", padx=5, fill="x", expand=True)

        self.s1207_entries = {}
        self.s1207_form = self.layouts.build_form(page, "S-1207", self.s1207_entries)

        ctk.CTkLabel(page, text="Gerenciador de Demonstrativos (ideDmDev)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.s1207_dm_manager = DmDevManager(page)
        self.s1207_dm_manager.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(page, text="Salvar S-1207 (Benefícios) na Fila", command=self.process_s1207, height=45, fg_color="#8E44AD").pack(pady=20)

        # Separator for batch processing
        sep = ctk.CTkFrame(page, height=2, fg_color="gray")
        sep.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(page, text="Processamento em Lote (S-1207)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)

        batch_frame = ctk.CTkFrame(page, fg_color="transparent")
        batch_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(batch_frame, text="Gerar Planilha Modelo (CSV)", command=lambda: self.generate_csv_template("S-1207"), height=35).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(batch_frame, text="Importar CSV (S-1207)", command=self.process_s1207_batch, height=35).pack(side="right", padx=10, fill="x", expand=True)

    def setup_s1210_tab(self):
        tab = self.tabview.tab("S-1210")
        
        # Split layout
        main_container = ctk.CTkFrame(tab, fg_color="transparent")
        main_container.pack(fill="both", expand=True)
        
        left_col = ctk.CTkFrame(main_container, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        right_col = ctk.CTkFrame(main_container, width=450)
        right_col.pack(side="right", fill="both", padx=(5, 0))
        right_col.pack_propagate(False)
        
        page = ctk.CTkScrollableFrame(left_col, fg_color="transparent")
        page.pack(fill="both", expand=True)
        
        self.s1210_qhistory = SideListPanel(right_col, self, evt_type="S-1210")
        self.s1210_qhistory.pack(fill="both", expand=True)
        
        # Header with Import
        h_frame = ctk.CTkFrame(page, fg_color="transparent")
        h_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(h_frame, text="S-1210 - Pagamentos (Data de Caixa)", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        ctk.CTkButton(h_frame, text="Importar XML para Retificar", command=lambda: self.import_rect_xml("S-1210"), fg_color="#F39C12").pack(side="right", padx=5)
        ctk.CTkButton(h_frame, text="Excluir via XML (S-3000)", command=lambda: self.import_exclude_xml("S-1210"), fg_color="#C0392B").pack(side="right")

        # Rectification Mode
        self.s1210_retif_frame = ctk.CTkFrame(page, fg_color="#34495E")
        self.s1210_retif_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(self.s1210_retif_frame, text="Tipo de Envio:").pack(side="left", padx=10)
        self.s1210_ind_retif = ctk.CTkOptionMenu(self.s1210_retif_frame, values=["1 - Original", "2 - Retificadora"], width=150)
        self.s1210_ind_retif.pack(side="left", padx=5)
        ctk.CTkLabel(self.s1210_retif_frame, text="Recibo Original:").pack(side="left", padx=10)
        self.s1210_nr_rec = ctk.CTkEntry(self.s1210_retif_frame, placeholder_text="Obrigatório se Retificadora", width=250)
        self.s1210_nr_rec.pack(side="left", padx=5, fill="x", expand=True)
        
        help_s1210 = ctk.CTkLabel(page, text="💡 Pagamentos: Informe a Data do Pagamento (Data de Caixa) e o ID do Demonstrativo correspondente do S-1200/S-1202.", font=ctk.CTkFont(size=11), text_color="gray")
        help_s1210.pack(padx=20, pady=5, anchor="w")

        self.s1210_entries = {}
        
        # Form Fields (Identity & Period)
        self.form_container = self.layouts.build_form(page, "S-1210", self.s1210_entries)
            
        ctk.CTkLabel(page, text="Gerenciador de Pagamentos (infoPgto)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        self.pgto_manager = InfoPgtoManager(page)
        self.pgto_manager.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(page, text="Salvar S-1210 (Pagamento) na Fila", command=self.process_s1210, height=45, fg_color="#F39C12").pack(pady=20)

        # Separator for batch processing
        sep = ctk.CTkFrame(page, height=2, fg_color="gray")
        sep.pack(fill="x", padx=20, pady=20)

        ctk.CTkLabel(page, text="Processamento em Lote (S-1210)", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)

        batch_frame = ctk.CTkFrame(page, fg_color="transparent")
        batch_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(batch_frame, text="Gerar Planilha Modelo (CSV)", command=lambda: self.generate_csv_template("S-1210"), height=35).pack(side="left", padx=10, fill="x", expand=True)
        ctk.CTkButton(batch_frame, text="Importar CSV (S-1210)", command=self.process_s1210_batch, height=35).pack(side="right", padx=10, fill="x", expand=True)

    def setup_xml_adj_tab(self):
        tab = self.tabview.tab("Ajuste XML")
        
        # Main container for the wizard
        self.wizard_container = ctk.CTkFrame(tab, fg_color="transparent")
        self.wizard_container.pack(fill="both", expand=True)
        
        # Progress Header
        self.progress_frame = ctk.CTkFrame(self.wizard_container, height=60, fg_color="#212F3D")
        self.progress_frame.pack(fill="x", padx=10, pady=10)
        
        self.step_labels = []
        steps = ["1. Importar", "2. Excluir (S-3000)", "3. Corrigir Dados", "4. Reenviar"]
        for i, s in enumerate(steps):
            lbl = ctk.CTkLabel(self.progress_frame, text=s, font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
            lbl.pack(side="left", expand=True)
            self.step_labels.append(lbl)
            
        # Step Content Container
        self.step_content = ctk.CTkFrame(self.wizard_container, fg_color="transparent")
        self.step_content.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Navigation Footer
        self.nav_frame = ctk.CTkFrame(self.wizard_container, height=60, fg_color="transparent")
        self.nav_frame.pack(fill="x", side="bottom", padx=20, pady=10)
        
        self.btn_prev = ctk.CTkButton(self.nav_frame, text="< Voltar", command=self.prev_correction_step, width=120, fg_color="#5D6D7E")
        self.btn_prev.pack(side="left")
        
        self.btn_next = ctk.CTkButton(self.nav_frame, text="Próximo >", command=self.next_correction_step, width=120, fg_color="#2E86C1")
        self.btn_next.pack(side="right")
        
        self.update_correction_ui()

    def setup_s1000_tab(self):
        tab = self.tabview.tab("S-1000")
        page = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        page.pack(fill="both", expand=True)

        ctk.CTkLabel(page, text="Evento S-1000 - Informações do Empregador", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        
        # Fields
        self.s1000_entries = {}
        fields = [
            ("iniValid", "Início Validade (AAAA-MM):", datetime.now().strftime("%Y-%m")),
            ("classTrib", "Classif. Tributária:", "85"),
            ("indCoop", "Indicativo Cooperativa:", "0"),
            ("indConstr", "Indicativo Construtora:", "0"),
            ("indDesFolha", "Desoneração Folha:", "0"),
            ("indOpcCP", "Opção Trib. Rural (indOpcCP):", "1"),
            ("indOptRegEletron", "Reg. Eletrônico (0/1):", "1"),
            ("indPorte", "Porte Empresa (1/N):", "N"),
            ("nmCtt", "Nome Contato:", "Responsável"),
            ("cpfCtt", "CPF Contato:", ""),
        ]
        
        for key, label, default in fields:
            f = ctk.CTkFrame(page, fg_color="transparent")
            f.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(f, text=label, width=200, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f)
            e.insert(0, default)
            e.pack(side="right", fill="x", expand=True)
            self.s1000_entries[key] = e
            
        ctk.CTkButton(page, text="Gerar e Salvar S-1000 (Pendente)", command=self.process_s1000, height=45, font=("Helvetica", 14), fg_color="#2874A6").pack(pady=20)

    def setup_s3000_tab(self):
        tab = self.tabview.tab("S-3000")
        page = ctk.CTkFrame(tab, fg_color="transparent")
        page.pack(fill="both", expand=True)

        label = ctk.CTkLabel(page, text="Gerenciar Eventos / Exclusão (S-3000)", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=10)
        
        # Form
        self.s3000_entries = {}
        self.form_container = self.layouts.build_form(page, "S-3000", self.s3000_entries)
            
        ctk.CTkButton(tab, text="Salvar Exclusão no Histórico (Pendente)", command=self.process_s3000, height=45, font=("Helvetica", 14), fg_color="#C0392B").pack(pady=20)

    def setup_config_tab(self):
        tab = self.tabview.tab("Config")
        page = ctk.CTkFrame(tab, fg_color="transparent")
        page.pack(fill="both", expand=True)

        label = ctk.CTkLabel(page, text="Configurações de Conexão", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=10)

        # Host
        f1 = ctk.CTkFrame(page, fg_color="transparent")
        f1.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f1, text="ACBr IP/Host:", width=150).pack(side="left")
        self.host_entry = ctk.CTkEntry(f1)
        self.host_entry.insert(0, self.config_data["host"])
        self.host_entry.pack(side="right", fill="x", expand=True)

        # Port
        f2 = ctk.CTkFrame(page, fg_color="transparent")
        f2.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f2, text="ACBr Port (TCP):", width=150).pack(side="left")
        self.port_entry = ctk.CTkEntry(f2)
        self.port_entry.insert(0, str(self.config_data["port"]))
        self.port_entry.pack(side="right", fill="x", expand=True)

        # Empregador
        f3 = ctk.CTkFrame(page, fg_color="transparent")
        f3.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f3, text="CNPJ/CPF Empregador:", width=150).pack(side="left")
        self.nrInsc_entry = ctk.CTkEntry(f3)
        self.nrInsc_entry.insert(0, self.config_data["nrInsc"])
        self.nrInsc_entry.pack(side="right", fill="x", expand=True)

        # Tipo Inscrição
        f_tp = ctk.CTkFrame(page, fg_color="transparent")
        f_tp.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_tp, text="Tipo Inscrição (1-CNPJ, 2-CPF):", width=150).pack(side="left")
        self.tpInsc_entry = ctk.CTkEntry(f_tp)
        self.tpInsc_entry.insert(0, self.config_data.get("tpInsc", "1"))
        self.tpInsc_entry.pack(side="right", fill="x", expand=True)

        # Ambiente
        f4 = ctk.CTkFrame(page, fg_color="transparent")
        f4.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f4, text="Ambiente eSocial:", width=150).pack(side="left")
        self.amb_menu = ctk.CTkOptionMenu(f4, values=["1 - Produção", "2 - Homologação"])
        current_amb = "1 - Produção" if self.config_data.get("tpAmb") == "1" else "2 - Homologação"
        self.amb_menu.set(current_amb)
        self.amb_menu.pack(side="right", fill="x", expand=True)

        # Pasta de XMLs
        f_xml = ctk.CTkFrame(page, fg_color="transparent")
        f_xml.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f_xml, text="Pasta Salvar XMLs:", width=150).pack(side="left")
        self.pasta_xml_entry = ctk.CTkEntry(f_xml)
        self.pasta_xml_entry.insert(0, self.config_data.get("pasta_xml", ""))
        self.pasta_xml_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ctk.CTkButton(f_xml, text="Selecionar", width=80, command=self.browse_xml_folder).pack(side="right")

        self.save_cfg_btn = ctk.CTkButton(page, text="💾 Salvar Todas as Configurações", command=self.update_config, height=40, fg_color="#2E86C1")
        page.pack(pady=10) # ensure spacing
        self.save_cfg_btn.pack(pady=20)
        
        # --- Email Settings Section ---
        email_frame = ctk.CTkFrame(tab)
        email_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(email_frame, text="📧 Configurações de Relatório por E-mail", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        email_grid = ctk.CTkFrame(email_frame, fg_color="transparent")
        email_grid.pack(fill="x", padx=20, pady=10)
        email_grid.grid_columnconfigure(1, weight=1)
        
        def add_email_row(label, key, row, is_password=False):
            ctk.CTkLabel(email_grid, text=label, width=150, anchor="w").grid(row=row, column=0, padx=5, pady=5, sticky="w")
            entry = ctk.CTkEntry(email_grid, show="*" if is_password else "")
            entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
            entry.insert(0, str(self.config_data.get(key, "")))
            return entry

        self.email_smtp = add_email_row("Servidor SMTP:", "smtp_host", 0)
        self.email_port = add_email_row("Porta (ex: 587):", "smtp_port", 1)
        self.email_sender = add_email_row("E-mail Remetente:", "sender_email", 2)
        self.email_pass = add_email_row("Senha de App:", "email_pass", 3, is_password=True)
        self.email_target = add_email_row("E-mail Destinatário:", "target_email", 4)
        
        self.test_email_btn = ctk.CTkButton(email_frame, text="🧪 Testar Envio de E-mail", command=self.test_email_config, fg_color="#8E44AD")
        self.test_email_btn.pack(pady=15)

    def browse_xml_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.pasta_xml_entry.delete(0, "end")
            self.pasta_xml_entry.insert(0, folder)

    def setup_manual_tab(self):
        tab = self.tabview.tab("Manual")
        
        page = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        page.pack(fill="both", expand=True, padx=10, pady=10)
        
        title = ctk.CTkLabel(page, text="📖 MANUAL DE OPERAÇÃO E GUIA DE USO", font=ctk.CTkFont(size=22, weight="bold"), text_color="#F39C12")
        title.pack(pady=(10, 20))

        sections = [
            ("🛠️ 1. Configurações Iniciais", 
             "Antes de começar, acesse a aba 'Config' e preencha:\n"
             "• ACBr IP/Host: Endereço do servidor ACBr (geralmente 127.0.0.1).\n"
             "• CNPJ/CPF Empregador: O número de inscrição da empresa.\n"
             "• Ambiente: Escolha '2 - Homologação' para testes ou '1 - Produção' para envios reais.\n"
             "• Teste de Certificado: Na aba 'Home', clique em 'Verificar Certificado A3' para validar se o Windows reconhece o seu token."),

            ("📝 2. Preenchimento de Eventos (S-1200, S-1202, etc.)",
             "Cada aba representa um tipo de remuneração. O fluxo padrão é:\n"
             "• Identificação: Preencha CPF, Período e Matrícula.\n"
             "• DICA: Se o trabalhador NÃO tiver matrícula (ex: estagiário ou cat 701), preencha obrigatoriamente Nome e Data de Nascimento.\n"
             "• Retificações: Se o evento já foi aceito e você deseja corrigir, mude para '2 - Retificadora' e informe o Número do Recibo anterior."),

            ("🏗️ 3. Múltiplos Demonstrativos (ID Demonstrativo)",
             "O sistema permite criar vários demonstrativos para o mesmo CPF:\n"
             "• Clique em '+ Adicionar Demonstrativo' para criar um novo bloco.\n"
             "• Cada bloco tem seu próprio ID (ex: 001, 002) e sua própria grade de rubricas.\n"
             "• Isso é útil quando o trabalhador tem múltiplas fontes de pagamento ou processos judiciais."),

            ("📑 4. Importação em Lote (CSV)",
             "Para enviar dezenas de trabalhadores de uma só vez:\n"
             "1. Vá na aba S-1200 e clique em 'Gerar Planilha Modelo'.\n"
             "2. Preencha o CSV (use ponto e vírgula como separador).\n"
             "3. Use a coluna 'TabelaRubrica' para definir a tabela (padrão: contindi).\n"
             "4. Clique em 'Importar e Salvar em Lote'. Todos os registros cairão no Histórico como 'Pendente'."),

            ("📜 5. Gestão através do Histórico",
             "O painel lateral (Quick History) é sua ferramenta de controle:\n"
             "• 🚀 Enviar: Assina e transmite o evento selecionado para o eSocial.\n"
             "• 📝 Carregar: Recupera os dados de um evento antigo de volta para os campos da tela (útil para correções).\n"
             "• 🔎 Ver: Abre os detalhes do retorno do governo. Se aceito, mostra as Bases de Cálculo (INSS/FGTS) processadas."),

            ("🚀 6. Consulta de Protocolos",
             "Após enviar, você receberá um número de Protocolo:\n"
             "• O sistema tenta consultar o resultado automaticamente.\n"
             "• Caso precise consultar manualmente, use o campo de texto na aba 'Home' e clique em 'Consultar Status do Lote'.\n"
             "• Uma vez aceito, o 'Número do Recibo' será gravado no banco de dados e aparecerá no histórico."),

            ("🏢 7. Configurando para um Novo CNPJ",
             "Se você estiver instalando o sistema para uma nova empresa ou CNPJ diferente:\n"
             "1. Vá na aba 'Config' e altere o 'CNPJ/CPF Empregador'.\n"
             "2. Confira se o 'Tipo Inscrição' está correto (1 para CNPJ, 2 para CPF).\n"
             "3. Na aba 'Home', clique em 'Verificar Certificado A3'. O sistema procurará no Windows um certificado que contenha o novo CNPJ.\n"
             "4. IMPORTANTE: O Certificado Digital A3 deve estar inserido e a senha (PIN) deve ser digitada na primeira transmissão do lote.\n"
             "5. Verifique o Ambiente: Comece sempre em 'Homologação' para garantir que os dados estão sendo aceitos antes de enviar para a Produção oficial.")
        ]

        for sec_title, sec_text in sections:
            s_frame = ctk.CTkFrame(page, corner_radius=10)
            s_frame.pack(fill="x", padx=10, pady=10)
            
            t_label = ctk.CTkLabel(s_frame, text=sec_title, font=ctk.CTkFont(size=14, weight="bold"), text_color="#3498DB")
            t_label.pack(padx=15, pady=(10, 5), anchor="w")
            
            c_label = ctk.CTkLabel(s_frame, text=sec_text, justify="left", wraplength=700)
            c_label.pack(padx=15, pady=(5, 15), anchor="w")

        footer = ctk.CTkLabel(page, text="IA_eSocial Monitor - Módulo Nativo v1.5", font=ctk.CTkFont(size=10), text_color="gray")
        footer.pack(pady=20)

    # --- Logic ---

    def update_config(self):
        self.config_data["host"] = self.host_entry.get().strip()
        self.config_data["port"] = int(self.port_entry.get().strip())
        self.config_data["nrInsc"] = self.nrInsc_entry.get().strip()
        self.config_data["tpInsc"] = self.tpInsc_entry.get().strip()
        self.config_data["tpAmb"] = "1" if "Produção" in self.amb_menu.get() else "2"
        
        # Email settings
        self.config_data["smtp_host"] = self.email_smtp.get().strip()
        try:
            self.config_data["smtp_port"] = int(self.email_port.get().strip())
        except:
            self.config_data["smtp_port"] = 587
            
        self.config_data["sender_email"] = self.email_sender.get().strip()
        self.config_data["email_pass"] = self.email_pass.get().strip()
        self.config_data["target_email"] = self.email_target.get().strip()
        
        self.save_config()
        self.env_label.configure(text=f"Ambiente: {self.get_env_name()}")
        self.log(f"Configurações salvas. Ambiente ativo: {self.get_env_name()}")
        messagebox.showinfo("Sucesso", "Configurações salvas com sucesso!")
        self.refresh_dashboard()

    def get_env_name(self):
        return "PRODUÇÃO" if self.config_data.get("tpAmb") == "1" else "HOMOLOGAÇÃO"

    def save_xml_auto(self, xml_content, event_type, cpf):
        """Salva o XML automaticamente se houver pasta configurada."""
        path = self.config_data.get("pasta_xml", "").strip()
        if not path or not os.path.exists(path):
            return
            
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            cpf_clean = re.sub(r'\D', '', str(cpf))
            filename = f"[{ts}]_{event_type}_{cpf_clean}.xml"
            full_path = os.path.join(path, filename)
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(xml_content)
            self.log(f"XML salvo em: {filename}")
        except Exception as e:
            self.log(f"Erro ao salvar XML em pasta: {e}")

    def process_s1000(self):
        import re
        def clean_id(val, size): 
            cleaned = re.sub(r'\D', '', str(val))
            return cleaned.zfill(size)

        data = {
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'nrInsc': re.sub(r'\D', '', str(self.config_data.get("nrInsc", ""))),
            'iniValid': self.s1000_entries["iniValid"].get(),
            'classTrib': self.s1000_entries["classTrib"].get(),
            'indCoop': self.s1000_entries["indCoop"].get(),
            'indConstr': self.s1000_entries["indConstr"].get(),
            'indDesFolha': self.s1000_entries["indDesFolha"].get(),
            'indOpcCP': self.s1000_entries["indOpcCP"].get(),
            'indOptRegEletron': self.s1000_entries["indOptRegEletron"].get(),
            'indPorte': self.s1000_entries["indPorte"].get(),
            'nmCtt': self.s1000_entries["nmCtt"].get(),
            'cpfCtt': clean_id(self.s1000_entries["cpfCtt"].get(), 11),
        }
        
        try:
            xml_content = generate_s1000_xml(data)
            # ID for S-1.3 (S-1000) - MUST use full 14 digits even if root-based
            full_nr = clean_id(self.config_data["nrInsc"], 14 if self.config_data["tpInsc"] == "1" else 11)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            rand = str(uuid.uuid4().int)[:5]
            evt_id = f"ID{self.config_data['tpInsc']}{full_nr}{timestamp}{rand}"
            self.db.save_event(None, evt_id, "S-1000", "EMPREGADOR", xml_content)
            self.save_xml_auto(xml_content, "S-1000", "EMPREGADOR")
            self.log(f"SUCESSO: S-1000 salvo como PENDENTE.")
            self.tabview.set("Histórico")
            self.refresh_history()
        except Exception as e:
            self.log(f"Erro ao gerar S-1000: {e}")

    def process_s1200(self):
        data = {k: e.get().strip() for k, e in self.s1200_entries.items()}
        data.update({
            'tpInsc': self.config_data.get("tpInsc", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'indRetif': self.s1200_ind_retif.get()[0],
            'nrRecEvt': self.s1200_nr_rec.get().strip(),
            'demonstrativos': self.s1200_dm_manager.get_data()
        })
        self._save_event_validated("S-1200", data)

    def generate_csv_template(self, evt_type="S-1200"):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            initialfile=f"modelo_{evt_type.lower()}.csv", 
            filetypes=[("CSV files", "*.csv")]
        )
        if not filename:
            return
            
        layout = self.layouts.get_layout(evt_type)
        if not layout:
            messagebox.showerror("Erro", f"Layout para {evt_type} não encontrado para gerar modelo.")
            return

        # 1. Start with static/mandatory headers from technical tags in JSON
        headers = []
        for section in layout.get("sections", []):
            for field in section.get("fields", []):
                headers.append(field["tag"])
        
        # 2. Add dynamic repeating block headers
        if evt_type in ["S-1200", "S-1202", "S-1207"]:
            headers.extend(["ideDmDev", "codRubr", "vrRubr", "ideTabRubr"])
        elif evt_type == "S-1210":
            # S-1210 headers for payments + simplified IR fields
            headers.extend(["dtPgto", "tpPgto", "perRef", "vrLiq", "ideDmDevs", "tpCR", "vrIRRF", "cpfDep", "vlrDedDep"])

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(headers)
                
                # Sample row based on event type
                sample = []
                # Fill based on static fields first
                for section in layout.get("sections", []):
                    for field in section.get("fields", []):
                        sample.append(field.get("default", ""))
                
                if evt_type == "S-1200":
                    sample.extend(["001", "1000", "2500.00", "contindi"])
                elif evt_type == "S-1207":
                    sample.extend(["001", "1000", "1500.00", "contindi"])
                elif evt_type == "S-1210":
                    sample.extend(["2026-02-28", "2", "2026-02", "2350.00", "001", "056107", "150.00", "", "0.00"])
                
                writer.writerow(sample)
                
            self.log(f"Modelo CSV para {evt_type} gerado em: {filename}")
        except Exception as e:
            self.log(f"Erro ao gerar planilha modelo {evt_type}: {e}")

    def load_for_edit(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione um evento no histórico para carregar.")
            return
            
        tree_item = self.tree.item(selected[0])
        evt_id = tree_item["values"][0]
        
        event_data = self.db.get_event_by_id(evt_id)
        if not event_data or not event_data["xml_content"]:
            messagebox.showerror("Erro", "Não foi possível recuperar o XML original.")
            return
        data = parse_esocial_xml(event_data["xml_content"])
        if not data:
            messagebox.showerror("Erro", "Falha ao interpretar o XML para edição.")
            return
            
        target_tab = event_data["type"]
        self.populate_form_from_data(target_tab, data)
        self.log(f"Evento {evt_id} carregado para edição na aba {target_tab}.")

    def populate_form_from_data(self, target_tab, data):
        """Centralized logic to fill UI forms from parsed XML data."""
        self.tabview.set(target_tab)
        
        # Determine the entries dictionary and managers based on tab
        entries = getattr(self, f"{target_tab.lower().replace('-', '')}_entries", {})
        ind_retif = getattr(self, f"{target_tab.lower().replace('-', '')}_ind_retif", None)
        nr_rec = getattr(self, f"{target_tab.lower().replace('-', '')}_nr_rec", None)
        dm_manager = getattr(self, f"{target_tab.lower().replace('-', '')}_dm_manager", None)
        
        # 1. Standard Header Fields (Retification)
        if ind_retif:
            ind_val = data.get('indRetif', '1')
            label = 'Retificadora' if ind_val == '2' else 'Original'
            ind_retif.set(f"{ind_val} - {label}")
        if nr_rec:
            nr_rec.delete(0, "end")
            nr_rec.insert(0, data.get('nrRecEvt', ''))
            
        # 2. Main Form Fields
        for k, v in data.items():
            if k in entries:
                widget = entries[k]
                if isinstance(widget, ctk.CTkEntry):
                    widget.delete(0, "end")
                    widget.insert(0, str(v) if v is not None else "")
                elif isinstance(widget, ctk.CTkOptionMenu):
                    widget.set(str(v))
                    
        # 3. Demonstrative Manager (S-1200, S-1202, S-1207)
        if dm_manager:
            dm_manager.clear() # Removes all default/existing blocks
            for dm in data.get('demonstrativos', []):
                new_block = dm_manager.add_dm(dm.get('ideDmDev', '001'))
                new_block.rubric_grid.clear() # Clear the single default row
                for r in dm.get('rubrics', []):
                    new_block.rubric_grid.add_row(
                        code=r.get('codRubr', ''),
                        amount=r.get('vrRubr', '0.00'),
                        table=r.get('ideTabRubr', 'contindi')
                    )
        
        # 4. Payment Manager (S-1210 specific)
        if target_tab == "S-1210":
            self.pgto_manager.clear()
            for pgto in data.get('pagamentos', []) or data.get('infoPgto', []):
                item = self.pgto_manager.add_pgto()
                # Fill pagamentos UI
                for k, v in pgto.items():
                    attr = getattr(item, k, None)
                    if isinstance(attr, ctk.CTkEntry):
                        attr.delete(0, "end"); attr.insert(0, str(v) if v is not None else "")
                    dems = [d.get('ideDmDev', '') for d in pgto['demonstrativos']]
                    item.ideDmDevs.delete(0, "end"); item.ideDmDevs.insert(0, ", ".join(dems))

    def process_s1202(self):
        data = {k: e.get().strip() for k, e in self.s1202_entries.items()}
        data.update({
            'tpInsc': self.config_data.get("tpInsc", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'indRetif': self.s1202_ind_retif.get()[0],
            'nrRecEvt': self.s1202_nr_rec.get().strip(),
            'demonstrativos': self.s1202_dm_manager.get_data()
        })
        self._save_event_validated("S-1202", data)

    def process_s1207(self):
        data = {k: e.get().strip() for k, e in self.s1207_entries.items()}
        data.update({
            'tpInsc': self.config_data.get("tpInsc", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'indRetif': self.s1207_ind_retif.get()[0],
            'nrRecEvt': self.s1207_nr_rec.get().strip(),
            'demonstrativos': self.s1207_dm_manager.get_data()
        })
        self._save_event_validated("S-1207", data)

    def process_s1210(self):
        data = {k: e.get().strip() for k, e in self.s1210_entries.items()}
        data.update({
            'tpInsc': self.config_data.get("tpInsc", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'indRetif': self.s1210_ind_retif.get()[0],
            'nrRecEvt': self.s1210_nr_rec.get().strip(),
            'pagamentos': self.pgto_manager.get_data()
        })
        self._save_event_validated("S-1210", data)

    def _save_event_validated(self, evt_type: str, data: dict) -> bool:
        """
        Central helper: generate XML → validate against XSD → save or show error.
        Returns True if saved successfully, False if validation failed or exception.
        """
        from lxml import etree
        try:
            # 1. Generate XML via central wrapper
            xml = generate_event_xml(evt_type, data)

            # 2. XSD Pre-validation (blocks invalid XMLs before they hit the DB)
            is_valid, errors = self.validator.validate(xml, evt_type)
            if is_valid is False and errors:  # None = no schema available (skip)
                # Format human-readable error dialog
                err_text = "\n".join(f"  • {e}" for e in errors[:15])  # cap at 15 lines
                if len(errors) > 15:
                    err_text += f"\n  ... e mais {len(errors) - 15} erro(s)."
                self.log(f"VALIDAÇÃO XSD FALHOU [{evt_type}]: {len(errors)} erro(s).")
                messagebox.showerror(
                    f"Erro de Validação XSD — {evt_type}",
                    f"O XML gerado não passou na validação XSD oficial.\n"
                    f"Corrija os campos indicados antes de salvar:\n\n{err_text}"
                )
                return False

            # 3. Extract event ID and persist
            root_el = etree.fromstring(xml.encode('utf-8'))
            evt_id = root_el[0].get('Id') or root_el.xpath('//@Id')[0]
            cpf = data.get('cpfTrab', data.get('cpfBenef', 'N/A'))

            self.db.save_event(None, evt_id, evt_type, cpf, xml)
            self.save_xml_auto(xml, evt_type, cpf)
            mode = 'RETIF' if data.get('indRetif') == '2' else 'ORIG'
            self.log(f"SUCESSO: {evt_type} ({mode}) ✔ XSD OK — salvo como PENDENTE.")
            self.refresh_history()
            self._check_and_remove_from_queue(evt_type)
            return True

        except Exception as e:
            self.log(f"ERRO ao gerar/salvar {evt_type}: {e}")
            messagebox.showerror("Erro Técnico", f"Falha ao gerar o evento {evt_type}:\n{e}")
            return False

    def process_s1200_batch(self):
        """Batch processing for S-1200."""
        filenames = filedialog.askopenfilenames(title="Selecione as planilhas CSV para S-1200", filetypes=[("CSV files", "*.csv")])
        if not filenames: return
        self._generic_rubric_batch_processor("S-1200", filenames)

    def process_s1202_batch(self):
        """Batch processing for S-1202."""
        filenames = filedialog.askopenfilenames(title="Selecione as planilhas CSV para S-1202", filetypes=[("CSV files", "*.csv")])
        if not filenames: return
        self._generic_rubric_batch_processor("S-1202", filenames)

    def process_s1207_batch(self):
        """Batch processing for S-1207 based on JSON metadata."""
        filenames = filedialog.askopenfilenames(title="Selecione as planilhas CSV para S-1207", filetypes=[("CSV files", "*.csv")])
        if not filenames: return
        self._generic_rubric_batch_processor("S-1207", filenames)

    def _generic_rubric_batch_processor(self, evt_type, filenames):
        """Helper to process S-1200, S-1202 or S-1207 batches using metadata-to-tag mapping."""
        layout = self.layouts.get_layout(evt_type)
        if not layout: return

        total_count = 0
        self.log(f"--- Iniciando Processamento Massivo {evt_type} ---")
        
        # Helper for case-insensitive and synonym lookups
        def get_val(row_lower, target_tag):
            synonyms = {
                "cpftrab": ["cpf", "cpftrabalho", "identificador"],
                "cpfbenef": ["cpf", "identificador", "cpfbeneficiario"],
                "nmtrab": ["nome", "nome completo", "trabalhador"],
                "perapur": ["periodo", "mes/ano", "data_ref", "mes_ano"],
                "vrrubr": ["valor", "vr_rem", "vlr_rem", "vlr_rubr", "vlr"],
                "codrubr": ["rubrica", "codigo", "cod_rubr", "código"],
                "idetabrubr": ["tabelarubrica", "tabela", "tab_rubr"],
                "idedmdev": ["identificador", "demonstrativo", "ide_dm_dev", "idedm"],
                "dtnascto": ["nascimento", "data nascimento", "nascimento_ddmmyyyy"],
                "codlotacao": ["lotacao", "cod_lotacao", "lotação"],
                "matricula": ["matricula", "matrícula", "nº beneficio", "nrbeneficio"]
            }
            target_low = target_tag.lower()
            if target_low in row_lower: return row_lower[target_low]
            for syn in synonyms.get(target_low, []):
                if syn.lower() in row_lower: return row_lower[syn.lower()]
            return None

        groups = {} # (cpf, period) -> { data: dict, demonstrativos: { ide_dm: [rubrics] } }

        for filename in filenames:
            try:
                delimiter = ';'
                # Encoding detection
                content_head = ""
                selected_enc = 'utf-8-sig'
                for enc in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
                    try:
                        with open(filename, 'r', encoding=enc) as f:
                            content_head = f.read(4096)
                            selected_enc = enc
                        break
                    except: continue

                if ',' in content_head and content_head.count(',') > content_head.count(';'):
                    delimiter = ','

                with open(filename, 'r', encoding=selected_enc, errors='replace') as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    for raw_row in reader:
                        # Normalize row keys to lower
                        if not raw_row: continue
                        row = {str(k).lower().strip(): str(v).strip() for k, v in raw_row.items() if k}
                        
                        # Essential fields
                        # S-1207 and S-1210 use 'cpfBenef'. S-1200 and S-1202 use 'cpfTrab'.
                        tag_cpf = "cpfBenef" if evt_type in ["S-1207", "S-1210"] else "cpfTrab"
                        raw_cpf = get_val(row, tag_cpf) or ""
                        cpf = re.sub(r'\D', '', str(raw_cpf))
                        period = get_val(row, "perApur") or ""
                        
                        if not cpf or not period: continue
                        
                        key = (cpf, period)
                        if key not in groups:
                            data = {
                                'tpAmb': self.config_data.get("tpAmb", "1"),
                                'nrInsc': self.config_data.get("nrInsc", ""),
                                'tpInsc': self.config_data.get("tpInsc", "1"),
                                'indRetif': '1',
                                'nrRecEvt': ''
                            }
                            # Map fields from layout
                            for section in layout["sections"]:
                                for field in section["fields"]:
                                    tag = field["tag"]
                                    val = get_val(row, tag)
                                    if val is not None: data[tag] = val
                            
                            # Ensure essential fields
                            data[tag_cpf] = cpf
                            data['perApur'] = period
                            
                            groups[key] = {'data': data, 'demonstrativos': {}}
                        
                        # Add Rubric
                        ide_dm = get_val(row, "ideDmDev") or "001"
                        if ide_dm not in groups[key]['demonstrativos']:
                            groups[key]['demonstrativos'][ide_dm] = []
                        
                        vr_raw = get_val(row, "vrRubr") or "0.00"
                        vr = str(vr_raw).replace(",", ".")
                        cod = str(get_val(row, "codRubr") or "").strip()
                        tab = str(get_val(row, "ideTabRubr") or "contindi").strip()
                        ind_ir = str(get_val(row, "indApurIR") or "0").strip()
                        
                        try:
                            if cod and float(vr) != 0:
                                groups[key]['demonstrativos'][ide_dm].append({
                                    'codRubr': cod, 'vrRubr': vr, 'ideTabRubr': tab, 'indApurIR': ind_ir
                                })
                        except ValueError: pass

                self.log(f"Processado arquivo: {os.path.basename(filename)}")
            except Exception as e:
                self.log(f"ERRO no arquivo {filename}: {e}")

        # Finalize grouping (move from groups dict to self.batch_queues)
        if evt_type not in self.batch_queues: self.batch_queues[evt_type] = []
        for key, grouped in groups.items():
            data = grouped['data']
            data['demonstrativos'] = [
                {'ideDmDev': ide, 'rubrics': rubrics} 
                for ide, rubrics in grouped['demonstrativos'].items() if rubrics
            ]
            if data['demonstrativos']:
                self.batch_queues[evt_type].append(data)
                total_count += 1

        panel = getattr(self, f"{evt_type.lower().replace('-', '')}_qhistory", None)
        if panel: panel.set_mode("QUEUE")
        self.log(f"--- Fim do processamento {evt_type}. {total_count} registros prontos. ---")

    def process_s1210_batch(self):
        """Specific batch processor for S-1210 (Pagamentos)."""
        filenames = filedialog.askopenfilenames(title="Selecione as planilhas CSV para S-1210", filetypes=[("CSV files", "*.csv")])
        if not filenames: return
        
        self.log(f"--- Iniciando Processamento Massivo S-1210 ---")
        total_count = 0
        groups = {} # (cpf, perApur) -> { data: dict, pagamentos: [] }

        def get_val_1210(row_lower, target_tag):
            synonyms = {
                "cpftrab": ["cpf", "cpftrabalho", "identificador"],
                "cpfbenef": ["cpf", "identificador", "cpfbeneficiario"],
                "nmtrab": ["nome", "nome completo", "trabalhador"],
                "perapur": ["periodo", "mes/ano", "data_ref", "mes_ano"],
                "idedmdevs": ["identificador", "demonstrativos", "demonstrativo", "idedmdev"],
                "dtpgto": ["data pgto", "data_pagamento", "pgto", "data"],
                "vrliq": ["valor liquido", "vlr_liquido", "liquido", "valor"],
                "perref": ["periodo ref", "periodoref", "ref"],
                "tppgto": ["tipo pgto", "tipo_pagamento", "tp_pgto"]
            }
            target_low = target_tag.lower()
            if target_low in row_lower: return row_lower[target_low]
            for syn in synonyms.get(target_low, []):
                if syn.lower() in row_lower: return row_lower[syn.lower()]
            return None

        for filename in filenames:
            try:
                delimiter = ';'
                content_head = ""
                selected_enc = 'utf-8-sig'
                for enc in ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
                    try:
                        with open(filename, 'r', encoding=enc) as f:
                            content_head = f.read(4096)
                            selected_enc = enc
                        break
                    except: continue

                if ',' in content_head and content_head.count(',') > content_head.count(';'):
                    delimiter = ','

                with open(filename, 'r', encoding=selected_enc, errors='replace') as f:
                    reader = csv.DictReader(f, delimiter=delimiter)
                    for raw_row in reader:
                        if not raw_row: continue
                        row = {str(k).lower().strip(): str(v).strip() for k, v in raw_row.items() if k}
                        
                        cpf = re.sub(r'\D', '', str(get_val_1210(row, "cpfTrab") or get_val_1210(row, "cpfBenef") or ""))
                        period = str(get_val_1210(row, "perApur") or "").strip()
                        if not cpf or not period: continue
                        
                        key = (cpf, period)
                        if key not in groups:
                            groups[key] = {
                                'data': {
                                    'tpAmb': self.config_data.get("tpAmb", "1"),
                                    'nrInsc': self.config_data.get("nrInsc", ""),
                                    'tpInsc': self.config_data.get("tpInsc", "1"),
                                    'cpfBenef': cpf,
                                    'perApur': period,
                                    'indRetif': '1',
                                    'nrRecEvt': ''
                                },
                                'pagamentos': []
                            }
                        
                        # Process payment line
                        dt_pgto = str(get_val_1210(row, "dtPgto") or "").strip()
                        if not dt_pgto: continue
                        
                        dems_val = get_val_1210(row, "ideDmDevs") or "001"
                        dems = [d.strip() for d in str(dems_val).split(",") if d.strip()]
                        
                        pgto = {
                            'dtPgto': dt_pgto,
                            'tpPgto': get_val_1210(row, "tpPgto") or "2",
                            'perRef': get_val_1210(row, "perRef") or period,
                            'vrLiq': str(get_val_1210(row, "vrLiq") or "0.00").replace(",", "."),
                            'demonstrativos': [{'ideDmDev': dem} for dem in dems],
                            'cr': get_val_1210(row, "tpCR") or "",
                            'vrIRRF': str(get_val_1210(row, "vrIRRF") or "0.00").replace(",", "."),
                            'cpfDep': get_val_1210(row, "cpfDep") or "",
                            'vlrDedDep': str(get_val_1210(row, "vlrDedDep") or "0.00").replace(",", ".")
                        }
                        groups[key]['pagamentos'].append(pgto)

                self.log(f"Processado arquivo: {os.path.basename(filename)}")
            except Exception as e:
                self.log(f"ERRO no arquivo {filename}: {e}")

        # Finalize and push to queue
        if "S-1210" not in self.batch_queues: self.batch_queues["S-1210"] = []
        for key, grouped in groups.items():
            data = grouped['data']
            data['pagamentos'] = grouped['pagamentos']
            if data['pagamentos']:
                self.batch_queues["S-1210"].append(data)
                total_count += 1
        
        panel = getattr(self, "s1210_qhistory", None)
        if panel: panel.set_mode("QUEUE")
        self.log(f"--- Fim do processamento S-1210. {total_count} registros prontos. ---")

    def _check_and_remove_from_queue(self, evt_type):
        """Internal helper to clean up the queue index after a manual save."""
        if self.current_review_index is not None:
            queue = self.batch_queues.get(evt_type, [])
            if 0 <= self.current_review_index < len(queue):
                queue.pop(self.current_review_index)
                self.current_review_index = None
                # Refresh panel
                panel = getattr(self, f"{evt_type.lower().replace('-', '')}_qhistory", None)
                if panel: panel.refresh()

    def save_queue_item_to_db(self, evt_type, data):
        """Helper for 'Save All' that persists a queue item to the DB using generate_event_xml."""
        from lxml import etree
        import re

        # Enrich data with config values that may be missing in batch-imported records
        data.setdefault('tpInsc', self.config_data.get('tpInsc', '1'))
        data.setdefault('nrInsc', self.config_data.get('nrInsc', ''))
        data.setdefault('tpAmb', self.config_data.get('tpAmb', '1'))
        data.setdefault('tpInscEstab', self.config_data.get('tpInsc', '1'))
        # nrInscEstab: use full 14-digit CNPJ from config if not already set
        if not data.get('nrInscEstab'):
            data['nrInscEstab'] = re.sub(r'\D', '', str(self.config_data.get('nrInsc', ''))).zfill(14)
        data.setdefault('indApuracao', '1')
        data.setdefault('indRetif', '1')
        data.setdefault('nrRecEvt', '')

        # Central wrapper: uses JSON layout if available, hardcoded generator as fallback
        xml_content = generate_event_xml(evt_type, data)

        # Extract Id from the generated XML
        root_el = etree.fromstring(xml_content.encode('utf-8'))
        evt_id = root_el[0].get('Id') or root_el.xpath('//@Id')[0]

        self.db.save_event(None, evt_id, evt_type, data['cpfTrab'], xml_content)
        self.save_xml_auto(xml_content, evt_type, data['cpfTrab'])
        self.log(f"  Salvo: [{evt_type}] CPF {data['cpfTrab']} → {evt_id[:30]}...")

    def load_xml_file(self, xml_key):
        filename = filedialog.askopenfilename(title=f"Selecione o {xml_key}", filetypes=[("XML files", "*.xml")])
        if not filename:
            return
            
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
            self.xml_data[xml_key] = filename
            
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] # strip namespace
                if tag == "cpfTrab":
                    self.xml_data["cpf"] = elem.text
                if tag == "perApur":
                    self.xml_data["perApur"] = elem.text
                if tag == "itensRemun":
                    # within itensRemun we have codRubr, ideTabRubr, vrRubr
                    cod_rubr = ""
                    vr_rubr = 0.0
                    for child in elem:
                        ctag = child.tag.split("}")[-1]
                        if ctag == "codRubr":
                            cod_rubr = child.text
                        if ctag == "vrRubr":
                            vr_rubr = float(child.text)
                            
                    if cod_rubr:
                        self.xml_data["rubrics"].append({
                            "source": xml_key,
                            "cod": cod_rubr,
                            "val": vr_rubr
                        })

            self.lbl_xml_status.configure(text=f"Carregado: {self.xml_data['xml1'] or '-'} | {self.xml_data['xml2'] or '-'}")
            self.lbl_cpf_xml.configure(text=f"CPF: {self.xml_data['cpf']} | Período: {self.xml_data['perApur']}")
            self.refresh_xml_grid()
            self.log(f"{xml_key} carregado com sucesso. Rubricas extraídas na tela.")
            
        except Exception as e:
            self.log(f"Erro ao abrir XML {xml_key}: {e}")

    def save_rubric_edits(self):
        for idx, entry in self.rubric_entries.items():
            if idx < len(self.xml_data["rubrics"]):
                try:
                    val_str = entry.get().replace(",", ".")
                    self.xml_data["rubrics"][idx]["val"] = float(val_str)
                except:
                    pass

    def delete_rubric(self, idx):
        self.save_rubric_edits()
        if 0 <= idx < len(self.xml_data["rubrics"]):
            self.log(f"Rubrica {self.xml_data['rubrics'][idx]['cod']} excluída visualmente do acerto.")
            self.xml_data["rubrics"].pop(idx)
        self.refresh_xml_grid()

    def refresh_xml_grid(self):
        for widget in self.xml_grid_frame.winfo_children():
            widget.destroy()
            
        self.rubric_entries.clear()
        
        # Headers
        ctk.CTkLabel(self.xml_grid_frame, text="Origem", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkLabel(self.xml_grid_frame, text="Cod. Rubrica", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(self.xml_grid_frame, text="Valor (R$)", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(self.xml_grid_frame, text="Ação", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=5, pady=5)
        
        row_idx = 1
        for idx, item in enumerate(self.xml_data["rubrics"]):
            source_lbl = "XML 1" if item["source"] == "xml1" else "XML 2"
            ctk.CTkLabel(self.xml_grid_frame, text=source_lbl).grid(row=row_idx, column=0, padx=5, pady=2)
            ctk.CTkLabel(self.xml_grid_frame, text=str(item["cod"])).grid(row=row_idx, column=1, padx=5, pady=2)
            
            entry = ctk.CTkEntry(self.xml_grid_frame, width=100)
            entry.insert(0, f"{item['val']:.2f}")
            entry.grid(row=row_idx, column=2, padx=5, pady=2)
            
            self.rubric_entries[idx] = entry
            
            btn_del = ctk.CTkButton(self.xml_grid_frame, text="Excluir", fg_color="red", hover_color="darkred", width=60, command=lambda i=idx: self.delete_rubric(i))
            btn_del.grid(row=row_idx, column=3, padx=5, pady=2)
            
            row_idx += 1

    def process_xml_adjustment(self):
        if not self.xml_data["cpf"]:
            self.log("ERRO: Nenhum CPF extraído dos XMLs.")
            return
            
        self.save_rubric_edits()
        
        # Consolida rubricas para não colocar rubrica duplicada no arquivo eSocial (que gera erro lá)
        final_rubrics = {}
        for item in self.xml_data["rubrics"]:
            cod = item["cod"]
            if cod in final_rubrics:
                final_rubrics[cod] += item["val"]
            else:
                final_rubrics[cod] = item["val"]
        
        rubrics_list = []
        for cod, val in final_rubrics.items():
            if val > 0:
                rubrics_list.append({'codRubr': cod, 'vrRubr': f"{val:.2f}", 'ideTabRubr': 'ContIndi'})
                
        data = {
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'cpfTrab': self.xml_data["cpf"],
            'perApur': self.xml_data["perApur"],
            'nrInscEstab': self.config_data.get("nrInsc", "") + "002151",
            'codLotacao': "1", # generic fallback
            'matricula': "",   # generic fallback
            'codCBO': "214120", # generic fallback
            'ideDmDev': "001",
            'codCateg': "701",
            'rubrics': rubrics_list
        }
        
        self.log(f"Gerando ajuste XML para CPF {data['cpfTrab']}...")
        xml_content = generate_event_xml("S-1200", data)
        
        try:
            xml_tree = ET.fromstring(xml_content)
            evt_id = xml_tree.get("Id", "ADJ_"+data['cpfTrab'])
            self.db.save_event(None, evt_id, "S-1200", data['cpfTrab'], xml_content)
            self.log(f"SUCESSO: Ajuste salvo como PENDENTE.")
            self.tabview.set("Histórico")
            self.refresh_history()
        except Exception as e:
            self.log(f"Falha ao salvar ajuste: {e}")

    def next_correction_step(self):
        if self.current_step == 1 and not self.correction_data["parsed_data"]:
            messagebox.showwarning("Aviso", "Por favor, carregue um XML primeiro.")
            return
            
        # Save data from current step before moving
        if self.current_step == 2:
            self.correction_data["original_receipt"] = self.corr_receipt_entry.get().strip()
        elif self.current_step == 3:
            self.save_correction_form_data()
            
        if self.current_step < 4:
            self.current_step += 1
            self.update_correction_ui()

    def prev_correction_step(self):
        if self.current_step > 1:
            self.current_step -= 1
            self.update_correction_ui()

    def update_correction_ui(self):
        # Update progress header colors
        for i, lbl in enumerate(self.step_labels):
            if i + 1 == self.current_step:
                lbl.configure(text_color="#10B981") # Active
            elif i + 1 < self.current_step:
                lbl.configure(text_color="#2E86C1") # Completed
            else:
                lbl.configure(text_color="gray") # Future
        
        # Clear current content
        for widget in self.step_content.winfo_children():
            widget.destroy()
            
        # Hide/Show buttons
        self.btn_prev.configure(state="normal" if self.current_step > 1 else "disabled")
        if self.current_step == 4:
            self.btn_next.configure(text="Finalizar", state="disabled")
        else:
            self.btn_next.configure(text="Próximo >", state="normal")

        # Load specific Step UI
        if self.current_step == 1: self.setup_step_1()
        elif self.current_step == 2: self.setup_step_2()
        elif self.current_step == 3: self.setup_step_3()
        elif self.current_step == 4: self.setup_step_4()

    def setup_step_1(self):
        """Step 1: Upload and Identify."""
        frame = ctk.CTkFrame(self.step_content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="Selecione o arquivo XML que deseja corrigir.", font=ctk.CTkFont(size=16)).pack(pady=10)
        
        btn_upload = ctk.CTkButton(frame, text="📁 Carregar XML do eSocial", height=50, command=self.load_xml_for_correction, fg_color="#27AE60")
        btn_upload.pack(pady=20)
        
        if self.correction_data["parsed_data"]:
            info_box = ctk.CTkFrame(frame, border_width=1, border_color="gray")
            info_box.pack(fill="x", pady=20, padx=50)
            
            p = self.correction_data["parsed_data"]
            txt = f"Evento Detectado: {self.correction_data['event_type']}\n"
            txt += f"CPF: {p.get('cpfTrab', p.get('cpfBenef', '-'))}\n"
            txt += f"Período: {p.get('perApur', '-')}\n"
            txt += f"Recibo Original: {self.correction_data['original_receipt'] or 'NÃO ENCONTRADO'}"
            
            ctk.CTkLabel(info_box, text=txt, justify="left", font=ctk.CTkFont(family="Consolas", size=12)).pack(padx=20, pady=20)
            
            if not self.correction_data["original_receipt"]:
                ctk.CTkLabel(frame, text="⚠️ Aviso: Recibo não encontrado no XML. Você precisará informá-lo manualmente no Passo 2.", text_color="orange").pack()

    def load_xml_for_correction(self):
        filename = filedialog.askopenfilename(title="Selecione o XML", filetypes=[("XML files", "*.xml")])
        if not filename: return
        
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            
            parsed = parse_esocial_xml(content)
            if not parsed:
                # Try reading with lxml directly to see if it's even a valid XML
                from lxml import etree
                tree = etree.fromstring(content.encode('utf-8'))
                tag = tree.tag.split("}")[-1]
                messagebox.showerror("Erro", f"O arquivo parece ser um XML eSocial ({tag}), mas não conseguimos extrair os dados automáticos.")
                return
            
            # Detect Type using S-1.3 official root tag names
            evt_type = "S-1200"
            if "evtRmnRPPS" in content: evt_type = "S-1202"    # S-1.3 (antes: evtServRPPS)
            elif "evtBenPrRP" in content: evt_type = "S-1207"  # S-1.3 (antes: evtBeneficio)
            elif "evtPgtos" in content: evt_type = "S-1210"
            
            self.correction_data = {
                "xml_path": filename,
                "parsed_data": parsed,
                "event_type": evt_type,
                "original_receipt": parsed.get('nrRecEvt'),
                "s3000_sent": False
            }
            self.log(f"XML carregado para correção: {evt_type} para CPF {parsed.get('cpfTrab')}")
            self.update_correction_ui()
            
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao carregar XML: {e}")

    def setup_step_2(self):
        """Step 2: Exclusion (S-3000)."""
        frame = ctk.CTkFrame(self.step_content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="Passo 1: Exclusão do Evento Anterior", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        ctk.CTkLabel(frame, text="Para corrigir um evento, primeiro devemos excluí-lo do portal eSocial.", wraplength=500).pack(pady=5)
        
        rec_frame = ctk.CTkFrame(frame)
        rec_frame.pack(fill="x", padx=100, pady=20)
        
        ctk.CTkLabel(rec_frame, text="Recibo a Excluir:").pack(side="left", padx=10, pady=10)
        self.corr_receipt_entry = ctk.CTkEntry(rec_frame, width=300)
        self.corr_receipt_entry.insert(0, self.correction_data["original_receipt"] or "")
        self.corr_receipt_entry.pack(side="right", padx=10, expand=True, fill="x")
        
        btn_send_s3000 = ctk.CTkButton(frame, text="🚀 Gerar e Enviar S-3000 Agora", height=45, fg_color="#C0392B", command=self.send_correction_s3000)
        btn_send_s3000.pack(pady=10)
        
        if self.correction_data["s3000_sent"]:
            ctk.CTkLabel(frame, text="✅ Exclusão enviada para a fila/Gov.", text_color="#10B981", font=ctk.CTkFont(weight="bold")).pack()
        
        ctk.CTkLabel(frame, text="💡 Dica: Após enviar, aguarde o processamento antes de prosseguir com o novo envio.", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=20)

    def send_correction_s3000(self):
        receipt = self.corr_receipt_entry.get().strip()
        if not receipt:
            messagebox.showerror("Erro", "É necessário o número do recibo para exclusão.")
            return
        
        data = {
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpInsc': self.config_data.get("tpInsc", "1"),
            'tpEvento': self.correction_data["event_type"],
            'nrRecEvt': receipt,
            'cpfTrab': self.correction_data["parsed_data"].get('cpfTrab', self.correction_data["parsed_data"].get('cpfBenef', '')),
            'perApur': self.correction_data["parsed_data"].get('perApur', '')
        }
        
        try:
            xml = generate_event_xml("S-3000", data)
            # Sign and Send immediately
            signed = self.native_sender.sign_event(xml, re.sub(r'\D', '', self.config_data["nrInsc"]))
            resp = self.native_sender.send_lote([signed], self.config_data["nrInsc"], self.config_data["tpAmb"])
            parsed_resp = self.native_sender.parse_response(resp)
            
            if parsed_resp["status"] in ["201", "202"]:
                self.log(f"S-3000 enviado com sucesso. Protocolo: {parsed_resp['protocol']}")
                self.correction_data["s3000_sent"] = True
                self.update_correction_ui()
                messagebox.showinfo("Sucesso", "Exclusão enviada com sucesso ao eSocial.")
            else:
                self.log(f"Falha ao enviar S-3000: {parsed_resp['desc']}")
                messagebox.showerror("Erro no Governo", f"Erro: {parsed_resp['desc']}\n{', '.join(parsed_resp['errors'])}")
        except Exception as e:
            self.log(f"Erro técnico no S-3000: {e}")
            messagebox.showerror("Erro", f"Falha técnica: {e}")

    def setup_step_3(self):
        """Step 3: Detailed Correction Form."""
        container = ctk.CTkScrollableFrame(self.step_content, fg_color="transparent")
        container.pack(fill="both", expand=True)
        
        ctk.CTkLabel(container, text="Passo 2: Correção dos Dados", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        p = self.correction_data["parsed_data"]
        self.corr_entries = {}
        
        # Identity Grid
        grid = ctk.CTkFrame(container)
        grid.pack(fill="x", padx=20, pady=10)
        grid.columnconfigure((0, 1), weight=1)
        
        fields = [
            ("CPF", "cpfTrab", p.get('cpfTrab', p.get('cpfBenef', ''))),
            ("Período", "perApur", p.get('perApur', '')),
            ("Matrícula", "matricula", p.get('matricula', '')),
            ("Categoria", "codCateg", p.get('codCateg', ''))
        ]
        
        for i, (label, key, val) in enumerate(fields):
            row, col = i // 2, i % 2
            f = ctk.CTkFrame(grid, fg_color="transparent")
            f.grid(row=row, column=col, padx=10, pady=5, sticky="ew")
            ctk.CTkLabel(f, text=label, width=100, anchor="w").pack(side="left")
            e = ctk.CTkEntry(f)
            e.insert(0, val or "")
            e.pack(side="right", fill="x", expand=True)
            self.corr_entries[key] = e
            
        # Rubrics Section
        ctk.CTkLabel(container, text="Rubricas / Valores", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))
        
        # We'll use a slightly different structure here to handle multi-DM
        self.corr_dm_managers = [] # In this wizard we recreate them
        
        # In a wizard we might want something simpler or reuse DmDevManager
        self.corr_dm_mgr = DmDevManager(container)
        self.corr_dm_mgr.pack(fill="x", padx=20, pady=5)
        self.corr_dm_mgr.clear()
        
        for dm in p.get('demonstrativos', []):
            item = self.corr_dm_mgr.add_dm(dm['ideDmDev'])
            item.rubric_grid.clear()
            for r in dm.get('rubrics', []):
                item.rubric_grid.add_row(r['codRubr'], r['vrRubr'], r.get('ideTabRubr', 'contindi'))
                
        ctk.CTkLabel(container, text="💡 Dica: Verifique todos os códigos e valores antes de avançar.", font=ctk.CTkFont(size=11), text_color="#3498DB").pack(pady=10)

    def setup_step_4(self):
        """Step 4: Final Transmission."""
        frame = ctk.CTkFrame(self.step_content, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="Passo 3: Finalização e Reenvio", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        ctk.CTkLabel(frame, text="Tudo pronto! Agora vamos gerar o novo arquivo corrigido (como Original) e transmitir ao eSocial.", wraplength=500).pack(pady=10)
        
        btn_send_final = ctk.CTkButton(frame, text="🚀 Transmitir Evento Corrigido", height=50, fg_color="#10B981", command=self.send_correction_final)
        btn_send_final.pack(pady=30)
        
        self.corr_final_status = ctk.CTkLabel(frame, text="Aguardando comando...")
        self.corr_final_status.pack()

    def save_correction_form_data(self):
        """Captures Step 3 UI values into self.correction_data before widgets are destroyed."""
        if not hasattr(self, 'corr_entries') or not self.corr_entries:
            return
            
        p = self.correction_data["parsed_data"]
        # Update flat fields
        for k, e in self.corr_entries.items():
            p[k] = e.get().strip()
            
        # Update rubrics from DmDevManager
        p['demonstrativos'] = self.corr_dm_mgr.get_data()
        self.log("Dados do formulário de correção capturados com sucesso.")

    def send_correction_final(self):
        # 1. Collect Data from Saved State (Not widgets anymore!)
        p = self.correction_data["parsed_data"]
        evt_type = self.correction_data["event_type"]
        
        data = {
            'cpfTrab': p.get('cpfTrab', ''),
            'perApur': p.get('perApur', ''),
            'matricula': p.get('matricula', ''),
            'codCateg': p.get('codCateg', ''),
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpInsc': self.config_data.get("tpInsc", "1"),
            'nrInscEstab': self.config_data.get("nrInsc", ""),
            'tpInscEstab': self.config_data.get("tpInsc", "1"),
            'indRetif': '1', # Always Original since we deleted the previous one
            'nrRecEvt': '', # No receipt for original
            'demonstrativos': p.get('demonstrativos', [])
        }
        
        try:
            xml = generate_event_xml(evt_type, data)
            
            # Save to history first
            from lxml import etree
            xml_tree = etree.fromstring(xml.encode('utf-8'))
            evt_id = xml_tree[0].get("Id")
            self.db.save_event(None, evt_id, evt_type, data['cpfTrab'], xml)
            
            # Transmit
            self.log(f"Transmitindo evento de correção {evt_id}...")
            signed = self.native_sender.sign_event(xml, re.sub(r'\D', '', self.config_data["nrInsc"]))
            resp = self.native_sender.send_lote([signed], self.config_data["nrInsc"], self.config_data["tpAmb"])
            parsed_resp = self.native_sender.parse_response(resp)
            
            if parsed_resp["status"] in ["201", "202"]:
                 self.corr_final_status.configure(text=f"✅ SUCESSO! Protocolo: {parsed_resp['protocol']}", text_color="#10B981")
                 messagebox.showinfo("Sucesso", f"Evento corrigido enviado com sucesso!\nProtocolo: {parsed_resp['protocol']}")
                 # Auto sync with DB
                 self.db.update_event_protocol(evt_id, parsed_resp['protocol'], "ENVIADO (Ajuste)")
                 self.refresh_history()
            else:
                 self.corr_final_status.configure(text=f"❌ FALHA: {parsed_resp['desc']}", text_color="#EF4444")
                 messagebox.showerror("Erro no Reenvio", f"O governo recusou o evento: {parsed_resp['desc']}")
                 
        except Exception as e:
            self.log(f"Erro no reenvio final: {e}")
            messagebox.showerror("Erro", f"Falha técnica no envio: {e}")

    def process_s3000(self):
        tp_evento = self.s3000_entries["tpEvento"].get().strip()
        nr_rec = self.s3000_entries["nrRecEvt"].get().strip()
        cpf = self.s3000_entries["cpfTrab"].get().replace(".", "").replace("-", "")
        per_apur = self.s3000_entries["perApur"].get().strip()
        
        if not nr_rec:
            self.log("ERRO: O Número do Recibo é obrigatório para o S-3000.")
            return
            
        data = {
            'tpAmb': self.config_data.get("tpAmb", "1"),
            'tpInsc': "1",
            'nrInsc': self.config_data.get("nrInsc", ""),
            'tpEvento': tp_evento,
            'nrRecEvt': nr_rec,
            'cpfTrab': cpf,
            'perApur': per_apur
        }
        
        self.log("Gerando XML para S-3000 (Exclusão)...")
        xml_content = generate_s3000_xml(data)
        
        try:
            from lxml import etree
            xml_tree = etree.fromstring(xml_content.encode('utf-8'))
            evt_id = xml_tree[0].get("Id") if xml_tree[0].get("Id") else ("EXT_S3000_"+data['cpfTrab'])
            
            self.db.save_event(None, evt_id, "S-3000", data['cpfTrab'], xml_content)
            self.save_xml_auto(xml_content, "S-3000", data['cpfTrab'])
            self.log(f"SUCESSO: Exclusão {evt_id} Salva como PENDENTE.")
            self.tabview.set("Histórico")
            self.refresh_history()
            
        except Exception as e:
            self.log(f"Erro ao salvar exclusão: {e}")

    def trigger_auto_consult(self, protocol):
        """Schedules an automatic consultation after 10 seconds."""
        self.log(f"AGUARDANDO 10s PARA CONSULTA AUTOMÁTICA DO PROTOCOLO {protocol}...")
        threading.Thread(target=self._auto_consult_worker, args=(protocol,), daemon=True).start()

    def _auto_consult_worker(self, protocol):
        time.sleep(10)
        # We need to call back into the main thread UI log
        self.perform_consultation(protocol)

    def process_consult_lote(self):
        protocol = self.protocol_entry.get().strip()
        if not protocol:
            self.log("ERRO: Informe um número de protocolo para consultar.")
            return
        self.perform_consultation(protocol)

    def perform_consultation(self, protocol):
        try:
            self.log(f"--- Consultando Protocolo {protocol} ---")
            resp_xml = self.native_sender.consult_lote(protocol, self.config_data["nrInsc"], self.config_data.get("tpAmb", "2"))
            
            res = self.native_sender.parse_response(resp_xml)
            if res["status"] in ["201", "202"]: 
                self.log(f"FECHAMENTO: {res['status']} - {res['desc']}")
                if res["protocol"]: self.log(f"REF: {res['protocol']}")
                
                # Atualizar eventos individuais no Banco de Dados
                for ev_res in res.get("event_results", []):
                    status_label = "Aceito" if ev_res["status"] == "201" else f"Rejeitado ({ev_res['status']})"
                    self.db.update_event_status(ev_res["id"], status_label, ev_res["nr_recibo"], ev_res.get("retorno_xml"))
                    self.log(f"  [DB] Evento {ev_res['id']} -> {status_label}")
            else:
                self.log(f"RESULTADO: {res['status']} - {res['desc']}")
            
            if res["errors"]:
                self.log("OCORRÊNCIAS NO PORTAL:")
                for err in res["errors"]:
                    self.log(f"  [!] {err}")
            elif res["status"] == "201":
                self.log("EVENTO ACEITO PELO GOVERNO! (Protocolo Processado)")
                
        except Exception as e:
            self.log(f"Erro na consulta: {e}")

    def setup_history_tab(self):
        tab = self.tabview.tab("Histórico")
        
        # Full history (no filter)
        self.main_history = SideListPanel(tab, self, fg_color="transparent")
        self.main_history.pack(fill="both", expand=True)
        
        # For compatibility with legacy methods
        self.tree = self.main_history.tree

    def refresh_history(self):
        # Refresh all active history instances
        if hasattr(self, 'main_history'): self.main_history.refresh()
        if hasattr(self, 's1200_qhistory'): self.s1200_qhistory.refresh()
        if hasattr(self, 's1202_qhistory'): self.s1202_qhistory.refresh()
        if hasattr(self, 's1207_qhistory'): self.s1207_qhistory.refresh()

    def view_totalizer(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione um evento processado para ver o retorno.")
            return
            
        tree_item = self.tree.item(selected[0])
        evt_id = tree_item["values"][0]
        
        event_data = self.db.get_event_by_id(evt_id)
        if not event_data or not event_data.get("retorno_xml"):
            # Fallback to simple response if no XML
            resp = event_data.get("last_response") or "Não há detalhes de resposta para este evento."
            messagebox.showinfo("Informação", resp)
            return
            
        # Show in a popup with XML parsing
        top = ctk.CTkToplevel(self)
        top.title(f"Retorno eSocial: {evt_id}")
        top.geometry("800x600")
        top.attributes("-topmost", True)
        
        txt = ctk.CTkTextbox(top)
        txt.pack(padx=10, pady=10, fill="both", expand=True)

        try:
            from lxml import etree
            xml_tree = etree.fromstring(event_data["retorno_xml"].encode('utf-8'))
            
            summary = "--- RESUMO DO RETORNO (S-5001 / S-5011) ---\n\n"
            
            # Bases de Cálculo
            bases = xml_tree.xpath("//*[local-name()='infoBaseCS' or local-name()='infoBaseCP']")
            if bases:
                summary += "BASES DE CÁLCULO ENCONTRADAS:\n"
                for b in bases:
                    val = b.xpath(".//*[local-name()='vrBcCP' or local-name()='vrBcFGTS']")[0].text if b.xpath(".//*[local-name()='vrBcCP' or local-name()='vrBcFGTS']") else "0.00"
                    summary += f"  - R$ {val}\n"
            
            # Ocorrências
            errors = xml_tree.xpath("//*[local-name()='descOcorr']")
            if errors:
                summary += "\nOCORRÊNCIAS / ERROS:\n"
                for err in errors:
                    summary += f"  [!] {err.text}\n"

            summary += f"\n\n--- XML NA ÍNTEGRA ---\n\n{event_data['retorno_xml']}"
            txt.insert("0.0", summary)
        except Exception as e:
            txt.insert("0.0", f"Erro ao processar XML de retorno: {e}\n\nConteúdo:\n{event_data['retorno_xml']}")

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected: return
        item_values = self.tree.item(selected[0])["values"]
        evt_id = item_values[0]
        status = str(item_values[3]).upper()

        if "PENDENTE" not in status:
            messagebox.showwarning("Bloqueio de Exclusão", 
                                 f"O evento {evt_id} não pode ser excluído porque seu status é '{status}'.\n"
                                 "A exclusão é permitida apenas para eventos 'PENDENTE' de envio.")
            return

        if messagebox.askyesno("Confirmar", f"Deseja remover o evento {evt_id} do histórico?"):
            self.db.delete_event(evt_id)
            self.log(f"Evento {evt_id} removido do histórico.")
            self.refresh_history()

    def send_selected_event(self):
        selected = self.tree.selection()
        if not selected:
            self.log("ERRO: Selecione um evento no histórico para enviar.")
            return
            
        tree_item = self.tree.item(selected[0])
        evt_id = tree_item["values"][0]
        
        event_data = self.db.get_event_by_id(evt_id)
        if not event_data: return

        # Determinar grupo S-1.3
        if event_data["type"] in ["S-1000", "S-1005", "S-1010", "S-1020", "S-1070"]:
            grupo = "1"
        elif event_data["type"] in ["S-1200", "S-1210", "S-1299"]:
            grupo = "3"
        else:
            grupo = "2"
            
        self.process_send_list([evt_id], "Selecionado", grupo=grupo)

    def send_all_pending(self):
        history = self.db.get_history()
        pending = [h for h in history if h["status"] == "Pendente"]
        
        if not pending:
            self.log("INFO: Não há eventos pendentes para enviar.")
            return
            
        to_send = [h["evt_id"] for h in pending]
        first_type = pending[0]["type"]
        
        if first_type in ["S-1000", "S-1005", "S-1010", "S-1020", "S-1070"]:
            grupo = "1"
        elif first_type in ["S-1200", "S-1210", "S-1299"]:
            grupo = "3"
        else:
            grupo = "2"

        if not messagebox.askyesno("Confirmar", f"Deseja enviar {len(to_send)} eventos pendentes agora?"):
            return
            
        self.process_send_list(to_send, "Lote Pendente", grupo=grupo)

    def import_exclude_xml(self, target_tab):
        filename = filedialog.askopenfilename(title=f"Importar XML de {target_tab} para EXCLUIR (S-3000)", filetypes=[("XML files", "*.xml")])
        if not filename: return
        
        try:
            with open(filename, "r", encoding='utf-8') as f:
                content = f.read()
            
            data = parse_esocial_xml(content)
            if not data or not data.get('nrRecEvt'):
                messagebox.showerror("Erro", "O XML selecionado não contém Número de Recibo (nrRecEvt) ou formato inválido.")
                return
            
            # Switch to S-3000 tab
            self.tabview.set("S-3000")
            
            # Populate S-3000 fields
            self.s3000_entries['tpEvento'].delete(0, "end")
            self.s3000_entries['tpEvento'].insert(0, target_tab)
            
            self.s3000_entries['nrRecEvt'].delete(0, "end")
            self.s3000_entries['nrRecEvt'].insert(0, data.get('nrRecEvt', ''))
            
            self.s3000_entries['cpfTrab'].delete(0, "end")
            self.s3000_entries['cpfTrab'].insert(0, data.get('cpfTrab', ''))
            
            if data.get('perApur'):
                self.s3000_entries['perApur'].delete(0, "end")
                self.s3000_entries['perApur'].insert(0, data.get('perApur', ''))
                
            self.log(f"Dados para S-3000 carregados via XML.")
            messagebox.showinfo("Importação Sucesso", f"Dados extraídos com sucesso do {target_tab}!\nRevise os campos na aba S-3000 e clique em 'Salvar S-3000 na Fila'.")
            
        except Exception as e:
            messagebox.showerror("Erro na Importação", f"Falha ao ler o XML: {e}")

    def import_rect_xml(self, target_tab):
        filename = filedialog.askopenfilename(title=f"Importar XML de {target_tab} para Retificar", filetypes=[("XML files", "*.xml")])
        if not filename: return
        
        try:
            with open(filename, "r", encoding='utf-8') as f:
                content = f.read()
            
            data = parse_esocial_xml(content)
            if not data:
                messagebox.showerror("Erro", "Não foi possível interpretar o XML. Verifique se é um evento S-1200, 1202, 1207 ou 1210 válido.")
                return
            
            self.populate_form_from_data(target_tab, data)
            
            # Force "Retificadora" mode regardless of original XML status
            if target_tab == "S-1200": self.s1200_ind_retif.set("2 - Retificadora")
            if target_tab == "S-1202": self.s1202_ind_retif.set("2 - Retificadora")
            if target_tab == "S-1207": self.s1207_ind_retif.set("2 - Retificadora")
            if target_tab == "S-1210": self.s1210_ind_retif.set("2 - Retificadora")

            self.log(f"XML Importado com SUCESSO. Modo RETIFICADORA ativado.")

        except Exception as e:
            self.log(f"Erro na importação: {e}")
            messagebox.showerror("Erro", f"Falha ao importar XML: {e}")

    def process_send_list(self, evt_ids, label, grupo="3"):
        self.log(f"--- Iniciando Envio ({label}) ---")
        temp_files = []
        try:
            for eid in evt_ids:
                event_data = self.db.get_event_by_id(eid)
                if event_data and event_data["xml_content"]:
                    temp_path = os.path.join(tempfile.gettempdir(), f"send_{uuid.uuid4().hex}.xml")
                    with open(temp_path, "w", encoding='utf-8') as f:
                        f.write(event_data["xml_content"])
                    temp_files.append((temp_path, eid, event_data["type"], event_data["cpf"]))

            if not temp_files:
                self.log("ERRO: Nenhum XML válido encontrado para os IDs selecionados.")
                return

            paths_only = [t[0] for t in temp_files]
            
            # Chama o motor nativo (1 PIN para todos)
            resp_xml = self.native_sender.sign_and_send_batch(
                paths_only, 
                self.config_data["nrInsc"], 
                self.config_data.get("tpAmb", "1"),
                grupo=grupo
            )
            
            res = self.native_sender.parse_response(resp_xml)
            if res["status"] in ["201", "202"]:
                self.log(f"SUCESSO NO ENVIO: {res['desc']}")
                if res["protocol"]:
                    self.db.save_batch(res["protocol"], self.config_data["nrInsc"], self.config_data.get("tpAmb", "1"))
                    # Atualizar os eventos originais com o protocolo
                    for _, eid, etype, ecpf in temp_files:
                        self.db.save_event(res["protocol"], eid, etype, ecpf, "") # Atualiza batch_id
                    
                    self.trigger_auto_consult(res["protocol"])
            else:
                self.log(f"FALHA NO ENVIO: {res['desc']}")
                for err in res["errors"]:
                    self.log(f"  > {err}")
        except Exception as e:
            self.log(f"Erro no processamento de envio: {e}")
        finally:
            for p, _, _, _ in temp_files:
                if os.path.exists(p): os.remove(p)
            self.refresh_history()

    def setup_reports_tab(self):
        tab = self.tabview.tab("Relatórios")
        tab.grid_columnconfigure(0, weight=1)
        
        frame = ctk.CTkFrame(tab)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="Gerador de Relatórios PDF", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        ctk.CTkLabel(frame, text="Selecione os filtros para o relatório de histórico.").pack(pady=5)
        
        filter_frame = ctk.CTkFrame(frame, fg_color="transparent")
        filter_frame.pack(pady=20)
        
        # Date Filters
        date_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        date_row.pack(pady=5)
        
        ctk.CTkLabel(date_row, text="Data Início (AAAA-MM-DD):").pack(side="left", padx=5)
        self.report_start = ctk.CTkEntry(date_row, width=120, placeholder_text="Ex: 2026-04-01")
        self.report_start.pack(side="left", padx=5)
        
        ctk.CTkLabel(date_row, text="Data Fim (AAAA-MM-DD):").pack(side="left", padx=5)
        self.report_end = ctk.CTkEntry(date_row, width=120, placeholder_text="Ex: 2026-04-30")
        self.report_end.pack(side="left", padx=5)
        
        # Type Filter
        type_row = ctk.CTkFrame(filter_frame, fg_color="transparent")
        type_row.pack(pady=5)
        
        ctk.CTkLabel(type_row, text="Tipo de Evento:").pack(side="left", padx=5)
        self.report_type = ctk.CTkComboBox(type_row, values=["Todos", "S-1000", "S-1200", "S-1202", "S-1210", "S-1207", "S-3000"])
        self.report_type.pack(side="left", padx=5)
        
        # Action Button
        self.btn_gen_report = ctk.CTkButton(frame, text="Gerar Relatório PDF", font=ctk.CTkFont(size=16, weight="bold"),
                                          command=self.generate_pdf_report, height=45, fg_color="#27AE60", hover_color="#1E8449")
        self.btn_gen_report.pack(pady=30)
        
        # --- NOVO: Seção S-5001 ---
        ctk.CTkLabel(frame, text="", height=1, fg_color="gray50").pack(fill="x", pady=20, padx=50) # Separator
        
        s5001_frame = ctk.CTkFrame(frame, fg_color="#2C3E50", corner_radius=10)
        s5001_frame.pack(fill="x", padx=40, pady=10)
        
        ctk.CTkLabel(s5001_frame, text="🔍 Conferência de INSS (Evento S-5001)", 
                      font=ctk.CTkFont(size=16, weight="bold"), text_color="#3498DB").pack(pady=10)
        
        ctk.CTkLabel(s5001_frame, text="Esta ferramenta lê os XMLs de retorno S-5001 e compara o cálculo do eSocial com a Folha enviados.", 
                      font=ctk.CTkFont(size=11)).pack(pady=2)
        
        path_row = ctk.CTkFrame(s5001_frame, fg_color="transparent")
        path_row.pack(pady=10, fill="x", padx=20)
        
        self.s5001_path_entry = ctk.CTkEntry(path_row, placeholder_text="Caminho da pasta com XMLs S-5001...")
        self.s5001_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(path_row, text="📁 Buscar", width=80, command=self.browse_s5001_folder).pack(side="right")
        
        self.btn_gen_s5001 = ctk.CTkButton(s5001_frame, text="📄 Gerar Relatório de Conferência", 
                                          command=self.generate_s5001_conferencia_report, 
                                          fg_color="#3498DB", hover_color="#2980B9", height=40, font=ctk.CTkFont(weight="bold"))
        self.btn_gen_s5001.pack(pady=15)

        ctk.CTkLabel(frame, text="* O relatório será salvo na pasta de sua preferência.", font=ctk.CTkFont(size=10)).pack()

    def generate_pdf_report(self):
        start = self.report_start.get()
        end = self.report_end.get()
        etype = self.report_type.get()
        
        # Validate dates if provided
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if start and not re.match(date_pattern, start):
            messagebox.showerror("Erro", "Data de início inválida. Use AAAA-MM-DD")
            return
        if end and not re.match(date_pattern, end):
            messagebox.showerror("Erro", "Data de fim inválida. Use AAAA-MM-DD")
            return
            
        history = self.db.get_history(evt_type=etype, start_date=start, end_date=end)
        
        if not history:
            messagebox.showinfo("Aviso", "Nenhum dado encontrado para os filtros selecionados.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"Relatorio_eSocial_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        
        if file_path:
            try:
                from report_generator import ESocialReport
                report = ESocialReport()
                filters = {
                    "Período": f"{start or 'Início'} até {end or 'Hoje'}",
                    "Tipo de Evento": etype,
                    "Total de Registros": len(history)
                }
                report.generate_report(history, file_path, filters=filters)
                messagebox.showinfo("Sucesso", f"Relatório gerado com sucesso!\nSalvo em: {file_path}")
                # Open directory
                path = os.path.realpath(os.path.dirname(file_path))
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao gerar PDF: {e}")

    def browse_s5001_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.s5001_path_entry.delete(0, "end")
            self.s5001_path_entry.insert(0, path)

    def generate_s5001_conferencia_report(self):
        folder = self.s5001_path_entry.get().strip()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Erro", "Selecione uma pasta válida contendo arquivos XML S-5001.")
            return

        xml_files = [f for f in os.listdir(folder) if f.lower().endswith(".xml")]
        if not xml_files:
            messagebox.showinfo("Aviso", "Nenhum arquivo XML encontrado na pasta selecionada.")
            return

        self.log(f"Processando {len(xml_files)} arquivos para conferência S-5001...")
        
        from report_generator import ESocialReport
        report = ESocialReport()
        data_to_report = []

        for f in xml_files:
            try:
                with open(os.path.join(folder, f), "r", encoding="utf-8") as file:
                    content = file.read()
                    # Reconhece tanto o nome técnico (evtBasesTrab/evt5001) quanto a string do evento
                    if any(x in content for x in ["evtBasesTrab", "evt5001", "S-5001", "S5001"]):
                        data = report.extract_s5001_data(content)
                        if data['cpf'] != '-':
                            data_to_report.append(data)
            except Exception as e:
                self.log(f"Erro ao ler arquivo {f}: {e}")

        if not data_to_report:
            messagebox.showwarning("Aviso", "Nenhum evento S-5001 válido foi identificado nos arquivos da pasta.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"Conferencia_INSS_S5001_{datetime.now().strftime('%Y%m%d')}.pdf"
        )

        if file_path:
            try:
                report.generate_s5001_report(data_to_report, file_path)
                messagebox.showinfo("Sucesso", f"Relatório de conferência gerado com sucesso!\nSalvo em: {file_path}")
                os.startfile(os.path.dirname(file_path))
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao gerar relatório S-5001: {e}")

    def test_email_config(self):
        """Tests the SMTP connection and credentials."""
        self.log("--- Testando Configurações de E-mail ---")
        try:
            host = self.email_smtp.get().strip()
            port = int(self.email_port.get().strip())
            user = self.email_sender.get().strip()
            pw = self.email_pass.get().strip()
            target = self.email_target.get().strip()

            if not all([host, port, user, pw, target]):
                messagebox.showerror("Erro", "Preencha todos os campos de e-mail antes de testar.")
                return

            server = smtplib.SMTP(host, port)
            server.set_debuglevel(1)
            server.starttls()
            server.login(user, pw)
            
            # Send a simple test message
            msg = MIMEText("Teste de conexão do sistema IA_eSocial efetuado com SUCESSO!", "plain", "utf-8")
            msg['Subject'] = "IA_eSocial - Teste de Conexão"
            msg['From'] = user
            msg['To'] = target
            
            server.sendmail(user, target, msg.as_string())
            server.quit()
            
            self.log("SUCESSO: Conexão SMTP estabelecida e e-mail de teste enviado!")
            messagebox.showinfo("Sucesso", "Conexão estabelecida! O e-mail de teste foi enviado.")
        except Exception as e:
            self.log(f"FALHA NO TESTE DE E-MAIL: {e}")
            messagebox.showerror("Erro de Conexão", f"Falha ao conectar ao servidor SMTP:\n{e}")

    def send_email_report(self):
        """Generates today's report and sends it to the configured email."""
        self.log("--- Iniciando Envio de Relatório Diário por E-mail ---")
        try:
            # 1. Config Check
            conf = self.config_data
            if not conf.get("sender_email") or not conf.get("email_pass") or not conf.get("target_email"):
                messagebox.showerror("Erro", "Configure seus dados de e-mail na aba 'Config' antes de enviar.")
                return

            # 2. Get Data (Today)
            today = datetime.now().strftime('%Y-%m-%d')
            history = self.db.get_history(start_date=today, end_date=today)
            
            if not history:
                if not messagebox.askyesno("Aviso", "Não há eventos registrados hoje. Deseja enviar um relatório geral de todo o histórico?"):
                    return
                history = self.db.get_history()

            # 3. Generate Temporary PDF
            temp_pdf = os.path.join(tempfile.gettempdir(), f"Resumo_eSocial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            report = ESocialReport()
            report.generate_report(history, temp_pdf, filters={"Filtro": "Resumo Automatizado", "Data": today})

            # 4. Construct Email
            msg = MIMEMultipart()
            msg['From'] = conf["sender_email"]
            msg['To'] = conf["target_email"]
            msg['Subject'] = f"IA_eSocial - Relatório de Envios ({today})"
            
            body = f"Olá,\n\nSegue em anexo o relatório consolidado de envios eSocial processados pelo sistema hoje ({today}).\n\nTotal de Registros: {len(history)}\n\nAtenciosamente,\nIA_eSocial Monitor"
            msg.attach(MIMEText(body, 'plain'))
            
            # Attach PDF
            with open(temp_pdf, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(temp_pdf)}")
            msg.attach(part)

            # 5. Send
            server = smtplib.SMTP(conf["smtp_host"], int(conf["smtp_port"]))
            server.starttls()
            server.login(conf["sender_email"], conf["email_pass"])
            server.sendmail(conf["sender_email"], conf["target_email"], msg.as_string())
            server.quit()

            # Cleanup
            if os.path.exists(temp_pdf): os.remove(temp_pdf)
            
            self.log(f"SUCESSO: Relatório enviado para {conf['target_email']}")
            messagebox.showinfo("Sucesso", f"Relatório enviado com sucesso para {conf['target_email']}!")

        except Exception as e:
            self.log(f"ERRO AO ENVIAR RELATÓRIO: {e}")
            messagebox.showerror("Erro no Envio", f"Ocorreu um erro ao tentar enviar o relatório por e-mail:\n{e}")

    def show_reports(self):
        self.tabview.set("Relatórios")


if __name__ == "__main__":
    app = ESocialApp()
    app.lift()
    app.attributes("-topmost", True)
    app.after(200, lambda: app.attributes("-topmost", False))
    app.mainloop()

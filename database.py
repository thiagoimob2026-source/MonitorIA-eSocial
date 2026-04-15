import sqlite3
import os
from datetime import datetime

class ESocialDatabase:
    def __init__(self, db_name="esocial_history.db"):
        # Local persistente em AppData para evitar erros de permissão
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.base_dir = os.path.join(appdata, "IA_eSocial")
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
        self.db_path = os.path.join(self.base_dir, db_name)
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        with self._get_connection() as conn:
            # Table for batches (identified by protocol)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol TEXT UNIQUE,
                    nr_insc_employer TEXT,
                    tp_amb TEXT,
                    status TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Table for individual events
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER,
                    evt_id TEXT UNIQUE,
                    type TEXT,
                    cpf TEXT,
                    nr_recibo TEXT,
                    status TEXT,
                    xml_content TEXT,
                    retorno_xml TEXT,
                    total_bruto REAL DEFAULT 0,
                    total_liquido REAL DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (batch_id) REFERENCES batches (id)
                )
            """)
            # Migration to add new columns if they don't exist
            try:
                conn.execute("ALTER TABLE events ADD COLUMN retorno_xml TEXT")
            except: pass 
            try:
                conn.execute("ALTER TABLE events ADD COLUMN total_bruto REAL DEFAULT 0")
            except: pass
            try:
                conn.execute("ALTER TABLE events ADD COLUMN total_liquido REAL DEFAULT 0")
            except: pass
            conn.commit()

    def save_batch(self, protocol, nr_insc, tp_amb):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO batches (protocol, nr_insc_employer, tp_amb, status) VALUES (?, ?, ?, ?)",
                (protocol, nr_insc, tp_amb, "Enviado")
            )
            conn.commit()
            return cursor.lastrowid

    def save_event(self, protocol, evt_id, evt_type, cpf, xml_content, total_bruto=0, total_liquido=0):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            batch_id = None
            if protocol:
                # Get batch_id from protocol
                cursor.execute("SELECT id FROM batches WHERE protocol = ?", (protocol,))
                row = cursor.fetchone()
                batch_id = row[0] if row else None
            
            status = "Pendente" if not protocol else "Processando"
            
            cursor.execute(
                "INSERT OR REPLACE INTO events (batch_id, evt_id, type, cpf, status, xml_content, total_bruto, total_liquido) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (batch_id, evt_id, evt_type, cpf, status, xml_content, total_bruto, total_liquido)
            )
            conn.commit()

    def update_event_status(self, evt_id, status, nr_recibo=None, retorno_xml=None):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE events SET status = ?, nr_recibo = ?, retorno_xml = ? WHERE evt_id = ?",
                (status, nr_recibo, retorno_xml, evt_id)
            )
            conn.commit()

    def get_history(self, evt_type=None, start_date=None, end_date=None):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT 
                    e.evt_id, e.type, e.cpf, e.status, e.nr_recibo, 
                    e.timestamp, b.protocol, e.xml_content, e.retorno_xml,
                    e.total_bruto, e.total_liquido
                FROM events e
                LEFT JOIN batches b ON e.batch_id = b.id
                WHERE 1=1
            """
            params = []
            if evt_type and evt_type != "Todos":
                query += " AND e.type = ?"
                params.append(evt_type)
            
            if start_date:
                query += " AND e.timestamp >= ?"
                params.append(start_date + " 00:00:00")
            
            if end_date:
                query += " AND e.timestamp <= ?"
                params.append(end_date + " 23:59:59")
            
            query += " ORDER BY e.timestamp DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_financial_totals(self, evt_id):
        """
        Extracts financial totals from return XML (S-5001/S-5011) if available.
        """
        event = self.get_event_by_id(evt_id)
        if not event or not event.get("retorno_xml"):
            return None
        
        from lxml import etree
        try:
            # Clean possible artifacts from response
            xml_str = event["retorno_xml"]
            idx = xml_str.find("<")
            if idx >= 0: xml_str = xml_str[idx:]
            
            root = etree.fromstring(xml_str.encode('utf-8'))
            
            # Helper to get numeric text
            def get_val(xpath):
                nodes = root.xpath(f"//*[local-name()='{xpath}']")
                return nodes[0].text if nodes else "0.00"

            totals = {
                "base_inss": "0.00",
                "valor_segurado": "0.00",
                "valor_patronal": "0.00",
                "tipo_retorno": "Desconhecido"
            }

            # If it contains S-5001 (Individual)
            if root.xpath("//*[local-name()='ideEvento' and *[local-name()='tpEvt' and text()='S-5001']]") or "S5001" in xml_str:
                totals["tipo_retorno"] = "Trabalhador (S-5001)"
                # Summing bases if there are multiple (very common)
                bases = root.xpath("//*[local-name()='vrBcCP01' or local-name()='vrBcCP']")
                totals["base_inss"] = "{:.2f}".format(sum(float(b.text or 0) for b in bases))
                totals["valor_segurado"] = get_val("vrCpSeg")
            
            # If it contains S-5011 (Company)
            elif "S5011" in xml_str:
                totals["tipo_retorno"] = "Empresa (S-5011)"
                totals["valor_segurado"] = get_val("vrCpSeg")
                totals["valor_patronal"] = get_val("vrCpPatr")
                # Base is usually sum of bases in ideEstab
                bases = root.xpath("//*[local-name()='vrBcCP']")
                totals["base_inss"] = "{:.2f}".format(sum(float(b.text or 0) for b in bases))

            return totals
        except Exception as e:
            print(f"Erro ao extrair totais: {e}")
            return None

    def get_event_by_id(self, evt_id):
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE evt_id = ?", (evt_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_dashboard_stats(self):
        """Returns counts for successes, failures, and pending items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Successes
            cursor.execute("SELECT COUNT(*) FROM events WHERE status LIKE 'Aceito%'")
            success = cursor.fetchone()[0]
            # Failures
            cursor.execute("SELECT COUNT(*) FROM events WHERE status LIKE 'Falha%' OR status LIKE 'Erro%' OR status LIKE 'Rejeitado%'")
            fail = cursor.fetchone()[0]
            # Pending
            cursor.execute("SELECT COUNT(*) FROM events WHERE status = 'PENDENTE'")
            pending = cursor.fetchone()[0]
            
            return {
                "success": success,
                "fail": fail,
                "pending": pending,
                "total": success + fail + pending
            }

    def delete_event(self, evt_id):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM events WHERE evt_id = ?", (evt_id,))
            conn.commit()

if __name__ == "__main__":
    db = ESocialDatabase()
    print("Database ready.")

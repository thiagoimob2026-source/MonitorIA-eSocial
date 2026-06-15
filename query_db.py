import os, sqlite3
appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
db_path = os.path.join(appdata, 'IA_eSocial', 'esocial_history.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT evt_id, type, status, xml_content FROM events WHERE cpf='53227280159' ORDER BY id DESC LIMIT 5")
import re
for row in c.fetchall():
    print(f"[{row['type']}] Status: {row['status']}")
    xml = row['xml_content']
    from lxml import etree
    try:
        root = etree.fromstring(xml.encode('utf-8'))
        def get_val(xpath):
            nodes = root.xpath(f"//*[local-name()='{xpath}']")
            return nodes[0].text if nodes else 'N/A'
        print(f"  indRetif: {get_val('indRetif')}")
        print(f"  perApur: {get_val('perApur')}")
        print(f"  perRef: {get_val('perRef')}")
        print(f"  ideDmDev: {get_val('ideDmDev')}")
        print(f"  tpPgto: {get_val('tpPgto')}")
    except Exception as e:
        print("Erro ao ler xml", e)
    print('----------------')

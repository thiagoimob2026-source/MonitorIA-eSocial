import PyInstaller.__main__
import os
import customtkinter
import shutil

def build():
    # Caminho do CustomTkinter para incluir os arquivos de tema (json/images)
    ctk_path = os.path.dirname(customtkinter.__file__)
    
    print(f"--- Iniciando Build Profissional ---")
    print(f"Local do CustomTkinter: {ctk_path}")

    # Limpar pastas de build anteriores
    if os.path.exists("dist"): shutil.rmtree("dist")
    if os.path.exists("build"): shutil.rmtree("build")

    PyInstaller.__main__.run([
        'main.py',
        '--name=IA_eSocial',
        '--windowed', # Não abrir console
        '--onefile',  # Gerar apenas um arquivo .exe
        '--collect-all=customtkinter', # Coletar tudo do ctk
        '--hidden-import=lxml',
        '--hidden-import=cryptography',
        '--clean',
        f'--add-data={ctk_path}{os.pathsep}customtkinter/',
        '--add-data=native/*;native/',
        '--add-data=schemas/*;schemas/',
    ])

    print("\n--- Build concluído com sucesso! ---")
    print("O executável está na pasta 'dist/IA_eSocial.exe'")

if __name__ == "__main__":
    build()

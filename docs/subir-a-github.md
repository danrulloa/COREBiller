# Subir COREBiller a GitHub

Esta carpeta es la copia preparada para el repositorio. Contiene código, pruebas, documentación y CSV ficticios. Se inicia únicamente con EjemploCORE, con dos servicios y un cliente ficticios; los nuevos Core están vacíos; no contiene clientes reales, bases SQLite, el Excel original, transcripciones ni capturas de pantalla.

1. Crea un repositorio vacío en tu cuenta de GitHub.
2. Sube el contenido de esta carpeta: app.py debe quedar en la raíz del repositorio, junto con README.md, static/, tests/ y los demás archivos.
3. Incluye .gitignore y .gitattributes. Si usas una carga manual, no añadas data/, outputs/ ni documentos privados: la carga web no aplica automáticamente las exclusiones de .gitignore.

También puedes usar Git desde esta carpeta, reemplazando USUARIO por tu cuenta y el nombre del repositorio si elegiste otro:

```powershell
git init -b main
git add .
git status --short
git commit -m "MVP local de COREBiller"
git remote add origin https://github.com/USUARIO/COREBiller.git
git push -u origin main
```

Revisa la lista de git status antes del commit. La licencia de distribución debe elegirla el propietario del proyecto.

Si el repositorio ya existe y esta carpeta tiene origin configurado, no repitas git init ni git remote add. Tras revisar y probar los cambios, usa git add, git commit y git push origin main.

## Arranque de una copia nueva

Instala Python 3.10 o posterior y ejecuta `python app.py`. No necesita paquetes externos. Abre http://127.0.0.1:8765 y pulsa Crear mi Core: basta con darle un nombre para entrar como administrador a un espacio vacío. También puedes explorar EjemploCORE, con datos ficticios.

## Verificación pública y privada

`python -B -m unittest discover -s tests -v` ejecuta las pruebas operativas sin depender del archivo privado. La prueba del libro queda explícitamente omitida cuando falta MicroAccounts.xlsx. Esto no significa que se haya comprobado toda la transcripción.

Para repetir la verificación privada, coloca tu MicroAccounts.xlsx localmente en la raíz (está excluido de Git) e instala `python -m pip install -r requirements-excel.txt`. El importador se ejecuta con `python scripts/import_microaccounts.py`; después inicia el servidor y ejecuta los scripts verify_excel_demo.py y verify_operational_demo.py. Estos scripts crean movimientos de demostración y no deben ejecutarse sobre cuentas de producción.

Los resultados quedan en outputs/ y las bases en data/, ambos excluidos del repositorio. No publiques esos archivos. La cobertura funcional y los casos todavía manuales están en casos-microcore.md.

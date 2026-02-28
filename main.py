import os
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.toast import toast

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from plyer import filechooser
    from jnius import autoclass, cast

KV_UI = '''
MDScreen:
    MDBoxLayout:
        orientation: "vertical"
        
        MDTopAppBar:
            title: "Envío Nativo Bluetooth"
            elevation: 4
            md_bg_color: app.theme_cls.primary_color

        MDBoxLayout:
            orientation: "vertical"
            padding: "20dp"
            spacing: "20dp"
            
            MDLabel:
                text: "Envía archivos usando el menú nativo de tu teléfono."
                halign: "center"
                theme_text_color: "Secondary"
                
            MDCard:
                orientation: "vertical"
                size_hint: 1, None
                height: "160dp"
                padding: "15dp"
                spacing: "15dp"
                elevation: 3
                
                MDLabel:
                    id: etiqueta_archivo
                    text: "Ningún archivo seleccionado"
                    halign: "center"
                    theme_text_color: "Hint"
                    
                MDBoxLayout:
                    orientation: "horizontal"
                    spacing: "10dp"
                    pos_hint: {"center_x": .5}
                    size_hint_x: None
                    width: self.minimum_width
                    
                    MDRectangleFlatButton:
                        text: "1. ELEGIR ARCHIVO"
                        on_release: app.seleccionar_archivo()
                        
                    MDRaisedButton:
                        id: btn_enviar
                        text: "2. ENVIAR"
                        disabled: True
                        on_release: app.compartir_archivo_nativo()
        
        Widget:
'''

class AplicacionCompartir(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.uri_archivo_seleccionado = None
        self.pantalla = Builder.load_string(KV_UI)
        
        if platform == 'android':
            self.solicitar_permisos_android()
        else:
            self.pantalla.ids.etiqueta_archivo.text = "Modo PC (simulación)"
            
        return self.pantalla

    def solicitar_permisos_android(self):
        permisos = [
            Permission.READ_EXTERNAL_STORAGE,
            Permission.READ_MEDIA_IMAGES,
            Permission.READ_MEDIA_VIDEO,
            Permission.READ_MEDIA_AUDIO
        ]
        request_permissions(permisos, self.on_permisos_result)

    def on_permisos_result(self, permissions, results):
        if all(results):
            self.actualizar_estado("Permisos listos")
        else:
            toast("Faltan permisos. Revisa ajustes.")

    def actualizar_estado(self, texto):
        Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.etiqueta_archivo, 'text', texto))

    def seleccionar_archivo(self):
        if platform == 'android':
            try:
                filechooser.open_file(on_selection=self.al_seleccionar_archivo)
            except Exception as e:
                toast(f"Fallo al abrir: {str(e)}")
        else:
            self.al_seleccionar_archivo(["/ruta/prueba.txt"])

    def al_seleccionar_archivo(self, seleccion):
        if seleccion and len(seleccion) > 0:
            self.uri_archivo_seleccionado = seleccion[0]
            nombre = os.path.basename(str(self.uri_archivo_seleccionado))
            Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.etiqueta_archivo, 'text', f"Archivo: {nombre}"))
            Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))
            toast("Archivo cargado")

    def compartir_archivo_nativo(self):
        if not self.uri_archivo_seleccionado:
            toast("Selecciona un archivo primero")
            return
            
        if platform == 'android':
            try:
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                File = autoclass('java.io.File')
                StrictMode = autoclass('android.os.StrictMode')
                
                # 1. Desactivamos la política estricta (permite file://)
                builder = StrictMode.VmPolicy.Builder()
                StrictMode.setVmPolicy(builder.build())
                
                # 2. Obtenemos la URI de forma segura
                ruta_o_uri = str(self.uri_archivo_seleccionado)
                
                if ruta_o_uri.startswith("content://"):
                    # Si ya es content URI, la usamos directamente
                    uri_android = Uri.parse(ruta_o_uri)
                else:
                    # Si es ruta de archivo, usamos Uri.fromFile (más robusto que concatenar)
                    archivo_java = File(ruta_o_uri)
                    uri_android = Uri.fromFile(archivo_java)
                
                # 3. Configuramos el Intent
                intent = Intent()
                intent.setAction(Intent.ACTION_SEND)
                intent.setType("*/*")
                intent.putExtra(Intent.EXTRA_STREAM, uri_android)
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                
                # 4. Mostramos el selector nativo
                chooser = Intent.createChooser(intent, "Enviar por...")
                actividad = cast('android.app.Activity', PythonActivity.mActivity)
                actividad.startActivity(chooser)
                
            except Exception as error:
                toast(f"ERROR: {str(error)}")
                # Para depuración, puedes imprimir el traceback completo en logcat
                import traceback
                traceback.print_exc()
        else:
            toast("Modo PC: no se puede enviar")

if __name__ == '__main__':
    AplicacionCompartir().run()

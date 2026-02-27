import os
import threading
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.list import TwoLineListItem
from kivymd.toast import toast

if platform == 'android':
    from android.permissions import request_permissions, Permission
    from jnius import autoclass
    from plyer import filechooser

UUID_PUERTO_SERIE = "00001101-0000-1000-8000-00805F9B34FB"

KV_UI = '''
MDScreen:
    MDBoxLayout:
        orientation: "vertical"
        
        MDTopAppBar:
            title: "Envío Bluetooth Pro"
            elevation: 4
            md_bg_color: app.theme_cls.primary_color

        MDLabel:
            id: etiqueta_estado
            text: "Estado: Esperando..."
            halign: "center"
            size_hint_y: None
            height: "40dp"
            theme_text_color: "Secondary"

        MDRaisedButton:
            text: "BUSCAR DISPOSITIVOS"
            pos_hint: {"center_x": .5}
            on_release: app.buscar_dispositivos()
            elevation: 2

        ScrollView:
            MDList:
                id: lista_dispositivos

        MDCard:
            orientation: "vertical"
            size_hint: 1, None
            height: "140dp"
            padding: "10dp"
            spacing: "10dp"
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
                    on_release: app.iniciar_envio_archivo()
'''

class AplicacionBluetooth(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.theme_style = "Light"
        self.socket_bt = None
        self.flujo_salida = None
        self.ruta_archivo_seleccionado = None
        
        self.pantalla = Builder.load_string(KV_UI)
        
        if platform == 'android':
            self.solicitar_permisos_android()
        else:
            self.actualizar_estado("Modo de prueba PC activado")
            
        return self.pantalla

    def mostrar_mensaje(self, texto):
        if platform == 'android':
            toast(texto)
        self.actualizar_estado(texto)

    def actualizar_estado(self, texto):
        Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.etiqueta_estado, 'text', texto))

    def solicitar_permisos_android(self):
        permisos = [
            Permission.BLUETOOTH_CONNECT, 
            Permission.BLUETOOTH_SCAN,
            Permission.ACCESS_FINE_LOCATION, 
            Permission.READ_EXTERNAL_STORAGE, 
            Permission.READ_MEDIA_IMAGES
        ]
        request_permissions(permisos)

    def buscar_dispositivos(self):
        if platform != 'android':
            self.mostrar_mensaje("El escaneo solo funciona en Android")
            return
            
        self.pantalla.ids.lista_dispositivos.clear_widgets()
        self.actualizar_estado("Buscando...")
        
        try:
            AdaptadorBluetooth = autoclass('android.bluetooth.BluetoothAdapter')
            adaptador = AdaptadorBluetooth.getDefaultAdapter()
            
            if not adaptador:
                self.mostrar_mensaje("Error: Teléfono sin Bluetooth")
                return
                
            if not adaptador.isEnabled():
                adaptador.enable()
                self.mostrar_mensaje("Activando Bluetooth... Presiona buscar de nuevo.")
                return
                
            dispositivos = adaptador.getBondedDevices().toArray()
            if len(dispositivos) == 0:
                self.mostrar_mensaje("No hay dispositivos emparejados.")
                return
                
            for dispositivo in dispositivos:
                # EXTRAEMOS MAC Y NOMBRE COMO TEXTO SIMPLE PARA EVITAR CRASH DE MEMORIA
                mac_dispositivo = dispositivo.getAddress()
                nombre_dispositivo = dispositivo.getName()
                item = TwoLineListItem(
                    text=nombre_dispositivo,
                    secondary_text=mac_dispositivo,
                    on_release=lambda x, mac=mac_dispositivo, nom=nombre_dispositivo: self.iniciar_conexion(mac, nom)
                )
                self.pantalla.ids.lista_dispositivos.add_widget(item)
                
            self.mostrar_mensaje("Dispositivos listados")
        except Exception as error:
            self.mostrar_mensaje(f"Fallo al escanear: {str(error)}")

    def iniciar_conexion(self, mac_dispositivo, nombre_dispositivo):
        self.mostrar_mensaje(f"Conectando a {nombre_dispositivo}...")
        # PASAMOS TEXTOS AL HILO SECUNDARIO, NO OBJETOS JAVA
        threading.Thread(target=self.conectar_a_dispositivo, args=(mac_dispositivo, nombre_dispositivo), daemon=True).start()

    def conectar_a_dispositivo(self, mac_dispositivo, nombre_dispositivo):
        try:
            from jnius import autoclass
            AdaptadorBluetooth = autoclass('android.bluetooth.BluetoothAdapter')
            
            # Pedimos el dispositivo a Android de forma segura desde dentro del hilo
            dispositivo_java = AdaptadorBluetooth.getDefaultAdapter().getRemoteDevice(mac_dispositivo)
            
            ClaseUUID = autoclass('java.util.UUID')
            uuid = ClaseUUID.fromString(UUID_PUERTO_SERIE)
            
            self.socket_bt = dispositivo_java.createRfcommSocketToServiceRecord(uuid)
            AdaptadorBluetooth.getDefaultAdapter().cancelDiscovery()
            
            self.socket_bt.connect()
            self.flujo_salida = self.socket_bt.getOutputStream()
            
            Clock.schedule_once(lambda dt: self.mostrar_mensaje(f"¡Conectado a {nombre_dispositivo}!"))
            
            if self.ruta_archivo_seleccionado:
                Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))
        except Exception as error:
            Clock.schedule_once(lambda dt: self.mostrar_mensaje(f"Error al conectar: {str(error)}"))
            if self.socket_bt:
                try: self.socket_bt.close()
                except: pass

    def seleccionar_archivo(self):
        if platform == 'android':
            try: 
                filechooser.open_file(on_selection=self.al_seleccionar_archivo)
            except Exception as e: 
                self.mostrar_mensaje(f"Fallo al abrir archivos: {str(e)}")
        else:
            self.al_seleccionar_archivo(["/ruta/prueba.txt"])

    def al_seleccionar_archivo(self, seleccion):
        if seleccion and len(seleccion) > 0:
            self.ruta_archivo_seleccionado = seleccion[0]
            nombre = os.path.basename(self.ruta_archivo_seleccionado)
            Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.etiqueta_archivo, 'text', nombre))
            self.mostrar_mensaje("Archivo cargado")
            
            if self.flujo_salida:
                Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))

    def iniciar_envio_archivo(self):
        if not self.ruta_archivo_seleccionado or not self.flujo_salida: 
            self.mostrar_mensaje("Falta seleccionar el archivo o conectar")
            return
            
        self.mostrar_mensaje("Enviando archivo...")
        self.pantalla.ids.btn_enviar.disabled = True
        threading.Thread(target=self.hilo_enviar_archivo, daemon=True).start()

    def hilo_enviar_archivo(self):
        try:
            with open(self.ruta_archivo_seleccionado, "rb") as archivo:
                while True:
                    fragmento = archivo.read(1024)
                    if not fragmento: break
                    self.flujo_salida.write(fragmento)
            self.flujo_salida.flush()
            Clock.schedule_once(lambda dt: self.mostrar_mensaje("¡Archivo enviado exitosamente!"))
        except Exception as error:
            Clock.schedule_once(lambda dt: self.mostrar_mensaje(f"Fallo al enviar: {str(error)}"))
        finally:
            Clock.schedule_once(lambda dt: setattr(self.pantalla.ids.btn_enviar, 'disabled', False))

if __name__ == '__main__':
    AplicacionBluetooth().run()

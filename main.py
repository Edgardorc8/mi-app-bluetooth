import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.utils import platform

# Solo importamos librerías específicas de Android si estamos en esa plataforma
if platform == 'android':
    from android.permissions import request_permissions, Permission
    from jnius import autoclass
    from plyer import filechooser

# UUID Estándar para SPP (Perfil de Puerto Serie) sobre RFCOMM
UUID_PUERTO_SERIE = "00001101-0000-1000-8000-00805F9B34FB"

class AplicacionBluetooth(App):
    def build(self):
        self.socket_bt = None
        self.flujo_salida = None
        self.ruta_archivo_seleccionado = None

        # --- INTERFAZ DE USUARIO ---
        self.raiz = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Etiqueta de estado principal
        self.etiqueta_estado = Label(text="Estado: Desconectado", size_hint_y=None, height=50)
        self.raiz.add_widget(self.etiqueta_estado)

        # Botón para buscar dispositivos (emparejados)
        self.btn_buscar = Button(text="Buscar Dispositivos Emparejados", size_hint_y=None, height=50)
        self.btn_buscar.bind(on_release=self.buscar_dispositivos)
        self.raiz.add_widget(self.btn_buscar)

        # Lista visual de dispositivos (ScrollView + GridLayout)
        self.vista_desplazable = ScrollView(size_hint=(1, 1))
        self.lista_dispositivos = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.lista_dispositivos.bind(minimum_height=self.lista_dispositivos.setter('height'))
        self.vista_desplazable.add_widget(self.lista_dispositivos)
        self.raiz.add_widget(self.vista_desplazable)

        # Controles para el manejo de archivos
        contenedor_archivos = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=10)
        
        self.btn_seleccionar_archivo = Button(text="Seleccionar Archivo")
        self.btn_seleccionar_archivo.bind(on_release=self.seleccionar_archivo)
        
        self.btn_enviar_archivo = Button(text="Enviar Archivo", disabled=True)
        self.btn_enviar_archivo.bind(on_release=self.iniciar_envio_archivo)
        
        contenedor_archivos.add_widget(self.btn_seleccionar_archivo)
        contenedor_archivos.add_widget(self.btn_enviar_archivo)
        self.raiz.add_widget(contenedor_archivos)

        # Etiqueta para mostrar el nombre del archivo elegido
        self.etiqueta_archivo = Label(text="Ningún archivo seleccionado", size_hint_y=None, height=30)
        self.raiz.add_widget(self.etiqueta_archivo)

        # Solicitar permisos al iniciar la app (solo en Android)
        if platform == 'android':
            self.solicitar_permisos_android()
        else:
            self.actualizar_estado("Aviso: Esta app requiere Android para el Bluetooth.")

        return self.raiz

    def actualizar_estado(self, texto):
        # Asegurarse de que la interfaz gráfica se actualice en el hilo principal
        Clock.schedule_once(lambda dt: setattr(self.etiqueta_estado, 'text', texto))

    def solicitar_permisos_android(self):
        # Permisos necesarios para Bluetooth y Archivos
        permisos = [
            Permission.BLUETOOTH_CONNECT,
            Permission.BLUETOOTH_SCAN,
            Permission.ACCESS_FINE_LOCATION,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.READ_MEDIA_IMAGES 
        ]
        request_permissions(permisos)

    def buscar_dispositivos(self, instancia):
        if platform != 'android':
            return

        self.lista_dispositivos.clear_widgets()
        self.actualizar_estado("Estado: Buscando dispositivos...")

        try:
            AdaptadorBluetooth = autoclass('android.bluetooth.BluetoothAdapter')
            adaptador = AdaptadorBluetooth.getDefaultAdapter()

            if not adaptador:
                self.actualizar_estado("Error: El teléfono no tiene Bluetooth")
                return

            # Encender Bluetooth si está apagado
            if not adaptador.isEnabled():
                adaptador.enable()
                self.actualizar_estado("Activando Bluetooth... intenta buscar de nuevo.")
                return

            # Obtener dispositivos vinculados (emparejados)
            dispositivos_vinculados = adaptador.getBondedDevices().toArray()
            
            if len(dispositivos_vinculados) == 0:
                self.actualizar_estado("No hay dispositivos emparejados.")
                return

            for dispositivo in dispositivos_vinculados:
                nombre = dispositivo.getName()
                direccion_mac = dispositivo.getAddress()
                boton_dispositivo = Button(text=f"{nombre}\n({direccion_mac})", size_hint_y=None, height=60)
                
                # Pasar el objeto dispositivo (Java) a la función de conexión al presionarlo
                boton_dispositivo.bind(on_release=lambda btn, disp=dispositivo: self.iniciar_conexion(disp))
                self.lista_dispositivos.add_widget(boton_dispositivo)

            self.actualizar_estado("Estado: Dispositivos encontrados")

        except Exception as error:
            self.actualizar_estado(f"Error al buscar: {str(error)}")

    def iniciar_conexion(self, dispositivo_java):
        self.actualizar_estado(f"Conectando a {dispositivo_java.getName()}...")
        # Conectar en un hilo separado para no congelar la pantalla
        threading.Thread(target=self.conectar_a_dispositivo, args=(dispositivo_java,), daemon=True).start()

    def conectar_a_dispositivo(self, dispositivo_java):
        try:
            ClaseUUID = autoclass('java.util.UUID')
            uuid = ClaseUUID.fromString(UUID_PUERTO_SERIE)
            
            # Crear socket RFCOMM seguro
            self.socket_bt = dispositivo_java.createRfcommSocketToServiceRecord(uuid)
            
            # Cancelar el descubrimiento de redes para acelerar la conexión
            AdaptadorBluetooth = autoclass('android.bluetooth.BluetoothAdapter')
            AdaptadorBluetooth.getDefaultAdapter().cancelDiscovery()

            # Conectar (Esto bloquea el hilo secundario hasta conectar o fallar)
            self.socket_bt.connect()
            self.flujo_salida = self.socket_bt.getOutputStream()
            
            nombre_dispositivo = dispositivo_java.getName()
            self.actualizar_estado(f"Estado: Conectado a {nombre_dispositivo}")
            
            # Habilitar botón de enviar si ya se había seleccionado un archivo
            if self.ruta_archivo_seleccionado:
                Clock.schedule_once(lambda dt: setattr(self.btn_enviar_archivo, 'disabled', False))

        except Exception as error:
            self.actualizar_estado("Error: No se pudo conectar.")
            print(f"Error de conexión Bluetooth: {error}")
            if self.socket_bt:
                try:
                    self.socket_bt.close()
                except:
                    pass

    def seleccionar_archivo(self, instancia):
        if platform == 'android':
            try:
                # Usa plyer para abrir el explorador de archivos nativo
                filechooser.open_file(on_selection=self.al_seleccionar_archivo)
            except Exception as error:
                self.etiqueta_archivo.text = f"Error al abrir explorador: {error}"
        else:
            # Simulación para pruebas en PC
            self.al_seleccionar_archivo(["/ruta/de/prueba/archivo_ejemplo.txt"])

    def al_seleccionar_archivo(self, seleccion):
        if seleccion and len(seleccion) > 0:
            self.ruta_archivo_seleccionado = seleccion[0]
            nombre_archivo = os.path.basename(self.ruta_archivo_seleccionado)
            Clock.schedule_once(lambda dt: setattr(self.etiqueta_archivo, 'text', f"Archivo: {nombre_archivo}"))
            
            # Si hay conexión activa, habilitar botón de enviar
            if self.flujo_salida:
                Clock.schedule_once(lambda dt: setattr(self.btn_enviar_archivo, 'disabled', False))

    def iniciar_envio_archivo(self, instancia):
        if not self.ruta_archivo_seleccionado or not self.flujo_salida:
            self.actualizar_estado("Falta seleccionar archivo o conectar Bluetooth.")
            return

        self.actualizar_estado("Enviando archivo...")
        self.btn_enviar_archivo.disabled = True
        
        # Enviar archivo en un hilo separado para no bloquear la app
        threading.Thread(target=self.hilo_enviar_archivo, daemon=True).start()

    def hilo_enviar_archivo(self):
        try:
            tamaño_archivo = os.path.getsize(self.ruta_archivo_seleccionado)
            bytes_enviados = 0

            with open(self.ruta_archivo_seleccionado, "rb") as archivo:
                while True:
                    
                    fragmento = archivo.read(1024)
                    if not fragmento:
                        break # Se llegó al fin del archivo
                    
                    # Escribir bytes en el flujo de salida hacia Java/Android
                    self.flujo_salida.write(fragmento)
                    
                    bytes_enviados += len(fragmento)
                    
            # Vaciar el búfer de salida para asegurar que todo se envíe
            self.flujo_salida.flush()
            self.actualizar_estado("Estado: Archivo enviado con éxito")

        except Exception as error:
            self.actualizar_estado("Error durante el envío del archivo.")
            print(f"Error enviando archivo: {error}")
        finally:
            Clock.schedule_once(lambda dt: setattr(self.btn_enviar_archivo, 'disabled', False))

if __name__ == '__main__':
    AplicacionBluetooth().run()
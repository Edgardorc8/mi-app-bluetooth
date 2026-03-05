"""
APLICACIÓN BLUETOOTH CLIENTE/SERVIDOR PARA ANDROID
Envío y recepción de archivos por RFCOMM
Versión mejorada con lista de dispositivos vinculados y transferencia funcional
"""
import os
import threading
import traceback
from datetime import datetime
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton, MDFlatButton
from kivymd.uix.label import MDLabel
from kivymd.uix.list import TwoLineListItem, MDList
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.dialog import MDDialog
from kivymd.toast import toast

# =============================================================================
# IMPORTACIONES ESPECÍFICAS DE ANDROID
# =============================================================================
if platform == 'android':
    from android.permissions import request_permissions, Permission, check_permission
    from android import api_version
    from plyer import filechooser
    from jnius import autoclass, cast, JavaException
else:
    # Simulación para pruebas en PC
    def request_permissions(*args, **kwargs):
        print("[Simulación] Permisos solicitados")

    class Permission:
        READ_EXTERNAL_STORAGE = "dummy"
        READ_MEDIA_IMAGES = "dummy"
        READ_MEDIA_VIDEO = "dummy"
        READ_MEDIA_AUDIO = "dummy"
        BLUETOOTH_CONNECT = "dummy"
        BLUETOOTH_SCAN = "dummy"
        ACCESS_FINE_LOCATION = "dummy"
        ACCESS_COARSE_LOCATION = "dummy"

    from plyer import filechooser

# =============================================================================
# CONSTANTES
# =============================================================================
UUID_SPP = "00001101-0000-1000-8000-00805F9B34FB"  # Estándar para RFCOMM
CHUNK_SIZE = 1024  # Tamaño de fragmento para envío

# =============================================================================
# INTERFAZ DE USUARIO (KV)
# =============================================================================
KV = '''
MDScreen:
    MDBoxLayout:
        orientation: "vertical"
        spacing: "10dp"
        padding: "10dp"

        MDTopAppBar:
            title: "Bluetooth Directo"
            elevation: 4
            md_bg_color: app.theme_cls.primary_color
            left_action_items: [["menu", lambda x: app.open_menu()]]

        MDLabel:
            id: status_label
            text: "Desconectado"
            halign: "center"
            theme_text_color: "Secondary"
            size_hint_y: None
            height: "40dp"

        MDBoxLayout:
            size_hint_y: None
            height: "60dp"
            spacing: "10dp"

            MDRaisedButton:
                id: btn_server
                text: "MODO SERVIDOR"
                on_release: app.start_server_mode()
                md_bg_color: app.theme_cls.primary_color
                disabled: True

            MDRaisedButton:
                id: btn_client
                text: "MODO CLIENTE"
                on_release: app.start_client_mode()
                md_bg_color: app.theme_cls.primary_color
                disabled: True

        ScrollView:
            MDList:
                id: device_list

        MDCard:
            orientation: "vertical"
            size_hint: 1, None
            height: "180dp"
            padding: "10dp"
            spacing: "10dp"
            elevation: 3

            MDLabel:
                id: file_label
                text: "Ningún archivo seleccionado"
                halign: "center"
                theme_text_color: "Hint"

            MDBoxLayout:
                orientation: "horizontal"
                spacing: "10dp"
                size_hint_x: None
                width: self.minimum_width
                pos_hint: {"center_x": 0.5}

                MDRectangleFlatButton:
                    id: btn_select_file
                    text: "SELECCIONAR ARCHIVO"
                    on_release: app.select_file()
                    disabled: True

                MDRaisedButton:
                    id: btn_send
                    text: "ENVIAR"
                    on_release: app.start_sending()
                    disabled: True

        MDBoxLayout:
            size_hint_y: None
            height: "50dp"
            spacing: "10dp"
            padding: "10dp"

            MDRectangleFlatButton:
                id: btn_scan
                text: "ESCANEAR"
                on_release: app.scan_devices()
                disabled: True

            MDRectangleFlatButton:
                id: btn_stop_server
                text: "DETENER SERVIDOR"
                on_release: app.stop_server()
                disabled: True
                md_bg_color: "red"
'''

# =============================================================================
# CLASE PRINCIPAL DE LA APLICACIÓN
# =============================================================================
class AplicacionBluetoothDirecto(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "Blue"
        self.screen = Builder.load_string(KV)
        self.device_list_widget = self.screen.ids.device_list

        # Variables de estado
        self.is_server = False
        self.is_client = False
        self.connected = False
        self.selected_file = None
        self.selected_device_mac = None
        self.selected_device_name = None

        # Objetos Bluetooth (inicializados en Android)
        self.bluetooth_adapter = None
        self.server_socket = None
        self.client_socket = None
        self.connected_thread = None

        # Para UI
        self.dialog = None

        if platform == 'android':
            self.request_permissions()
        else:
            self.update_status("MODO PC - Simulación")

        return self.screen

    # -------------------------------------------------------------------------
    # MANEJO DE PERMISOS
    # -------------------------------------------------------------------------
    def request_permissions(self):
        """Solicita todos los permisos necesarios según la versión de Android"""
        permissions = [
            Permission.READ_EXTERNAL_STORAGE,
            Permission.READ_MEDIA_IMAGES,
            Permission.READ_MEDIA_VIDEO,
            Permission.READ_MEDIA_AUDIO,
        ]

        # Permisos de Bluetooth según API level
        if api_version >= 31:  # Android 12+
            permissions.extend([
                Permission.BLUETOOTH_CONNECT,
                Permission.BLUETOOTH_SCAN,
            ])
            # No es obligatorio, pero por compatibilidad
            permissions.append(Permission.ACCESS_FINE_LOCATION)
        else:
            # Android 11 y anteriores
            permissions.extend([
                Permission.BLUETOOTH,
                Permission.BLUETOOTH_ADMIN,
                Permission.ACCESS_FINE_LOCATION,
                Permission.ACCESS_COARSE_LOCATION,
            ])

        request_permissions(permissions, self.on_permissions_result)

    def on_permissions_result(self, permissions, results):
        if all(results):
            self.update_status("Permisos concedidos")
            self.init_bluetooth()
        else:
            toast("Faltan permisos necesarios. Revisa ajustes.")

    # -------------------------------------------------------------------------
    # INICIALIZACIÓN DE BLUETOOTH
    # -------------------------------------------------------------------------
    def init_bluetooth(self):
        """Inicializa el adaptador Bluetooth de Android"""
        try:
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            self.bluetooth_adapter = BluetoothAdapter.getDefaultAdapter()

            if not self.bluetooth_adapter:
                toast("Este dispositivo no soporta Bluetooth")
                return

            if not self.bluetooth_adapter.isEnabled():
                # Intentar encender Bluetooth
                self.bluetooth_adapter.enable()
                toast("Activando Bluetooth...")

            self.update_status("Bluetooth listo")
            # Habilitar botones según modo
            self.screen.ids.btn_server.disabled = False
            self.screen.ids.btn_client.disabled = False

        except Exception as e:
            toast(f"Error al iniciar Bluetooth: {str(e)}")

    # -------------------------------------------------------------------------
    # UTILIDADES DE UI
    # -------------------------------------------------------------------------
    def update_status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.screen.ids.status_label, 'text', text))

    def show_dialog(self, title, text):
        if not self.dialog:
            self.dialog = MDDialog(
                title=title,
                text=text,
                buttons=[MDFlatButton(text="OK", on_release=lambda x: self.dialog.dismiss())]
            )
        else:
            self.dialog.title = title
            self.dialog.text = text
        self.dialog.open()

    # -------------------------------------------------------------------------
    # MODO SERVIDOR
    # -------------------------------------------------------------------------
    def start_server_mode(self):
        """Inicia el modo servidor: espera conexiones entrantes"""
        if not self.bluetooth_adapter:
            toast("Bluetooth no disponible")
            return

        self.is_server = True
        self.is_client = False
        self.screen.ids.btn_server.md_bg_color = "green"
        self.screen.ids.btn_client.md_bg_color = self.theme_cls.primary_color
        self.screen.ids.btn_stop_server.disabled = False
        self.screen.ids.btn_select_file.disabled = True  # El servidor no selecciona archivo
        self.screen.ids.btn_scan.disabled = True  # El servidor no escanea

        self.update_status("Servidor: Esperando conexión...")
        threading.Thread(target=self._server_thread, daemon=True).start()

    def _server_thread(self):
        """Hilo del servidor: crea socket y acepta conexión"""
        try:
            UUID = autoclass('java.util.UUID')
            uuid = UUID.fromString(UUID_SPP)

            # Crear socket servidor
            self.server_socket = self.bluetooth_adapter.listenUsingRfcommWithServiceRecord(
                "AppBluetoothServer", uuid)

            # Aceptar conexión (bloqueante)
            self.client_socket = self.server_socket.accept()

            # Conexión establecida
            Clock.schedule_once(lambda dt: self._on_server_connected())

        except Exception as e:
            error_msg = f"Error en servidor: {str(e)}"
            Clock.schedule_once(lambda dt: toast(error_msg))
            traceback.print_exc()
        finally:
            # Cerramos el server socket después de aceptar uno
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass

    def _on_server_connected(self):
        """Se llama cuando un cliente se conecta al servidor"""
        self.connected = True
        self.update_status("Servidor: Cliente conectado")
        toast("¡Cliente conectado!")

        # Iniciar hilo de recepción (el servidor recibe archivos)
        self.connected_thread = threading.Thread(
            target=self._receive_file_thread, daemon=True)
        self.connected_thread.start()

    def stop_server(self):
        """Detiene el servidor y cierra sockets"""
        self.is_server = False
        self.connected = False
        self.screen.ids.btn_stop_server.disabled = True
        self.screen.ids.btn_server.md_bg_color = self.theme_cls.primary_color

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        self.update_status("Servidor detenido")

    # -------------------------------------------------------------------------
    # MODO CLIENTE
    # -------------------------------------------------------------------------
    def start_client_mode(self):
        """Activa modo cliente: permite escanear y conectarse"""
        if not self.bluetooth_adapter:
            toast("Bluetooth no disponible")
            return

        self.is_client = True
        self.is_server = False
        self.screen.ids.btn_client.md_bg_color = "green"
        self.screen.ids.btn_server.md_bg_color = self.theme_cls.primary_color
        self.screen.ids.btn_stop_server.disabled = True  # No aplica en cliente
        self.screen.ids.btn_select_file.disabled = False
        self.screen.ids.btn_scan.disabled = False  # Habilitar escaneo
        self.screen.ids.device_list.clear_widgets()

        self.update_status("Cliente: Busca dispositivos")
        toast("Modo cliente activado")

    def scan_devices(self):
        """Escanea y muestra dispositivos emparejados"""
        if not self.is_client:
            toast("Activa modo cliente primero")
            return

        if not self.bluetooth_adapter:
            return

        # Verificar permisos según API (opcional pero recomendado)
        if platform == 'android':
            if api_version >= 31:
                if not check_permission(Permission.BLUETOOTH_CONNECT):
                    toast("Permiso BLUETOOTH_CONNECT no concedido")
                    self.request_permissions()
                    return
            else:
                if not check_permission(Permission.BLUETOOTH):
                    toast("Permiso BLUETOOTH no concedido")
                    self.request_permissions()
                    return

        self.update_status("Escaneando...")
        self.screen.ids.device_list.clear_widgets()

        try:
            # Cancelar descubrimiento si está activo
            self.bluetooth_adapter.cancelDiscovery()

            # Obtener dispositivos emparejados
            bonded_devices = self.bluetooth_adapter.getBondedDevices()
            if bonded_devices:
                devices_array = bonded_devices.toArray()
                for device in devices_array:
                    name = device.getName()
                    mac = device.getAddress()
                    item = TwoLineListItem(
                        text=name if name else "Sin nombre",
                        secondary_text=mac,
                        on_release=lambda x, d=device: self.connect_to_device(d)
                    )
                    self.screen.ids.device_list.add_widget(item)

                self.update_status(f"{len(devices_array)} dispositivos encontrados")
            else:
                self.update_status("No hay dispositivos emparejados")

        except Exception as e:
            toast(f"Error al escanear: {str(e)}")
            traceback.print_exc()

    def connect_to_device(self, device):
        """Intenta conectar a un dispositivo seleccionado"""
        if not self.is_client:
            return

        self.selected_device_mac = device.getAddress()
        self.selected_device_name = device.getName() or "Desconocido"

        self.update_status(f"Conectando a {self.selected_device_name}...")
        threading.Thread(target=self._connect_thread, args=(device,), daemon=True).start()

    def _connect_thread(self, device):
        """Hilo de conexión del cliente"""
        try:
            UUID = autoclass('java.util.UUID')
            uuid = UUID.fromString(UUID_SPP)

            # Cancelar descubrimiento
            self.bluetooth_adapter.cancelDiscovery()

            # Crear socket
            socket = device.createRfcommSocketToServiceRecord(uuid)
            socket.connect()

            self.client_socket = socket

            Clock.schedule_once(lambda dt: self._on_client_connected())

        except Exception as e:
            error_msg = f"Error al conectar: {str(e)}"
            Clock.schedule_once(lambda dt: toast(error_msg))
            traceback.print_exc()

    def _on_client_connected(self):
        """Se llama cuando el cliente se conecta exitosamente"""
        self.connected = True
        self.update_status(f"Conectado a {self.selected_device_name}")
        toast("¡Conectado!")

        # Habilitar botón de enviar
        self.screen.ids.btn_send.disabled = False

        # El cliente no inicia hilo de recepción porque solo envía archivos.
        # Si se quisiera comunicación bidireccional, habría que iniciarlo.

    # -------------------------------------------------------------------------
    # SELECCIÓN DE ARCHIVO (Cliente)
    # -------------------------------------------------------------------------
    def select_file(self):
        """Abre el selector de archivos nativo"""
        if not self.is_client:
            toast("Activa modo cliente primero")
            return

        try:
            filechooser.open_file(on_selection=self._on_file_selected)
        except Exception as e:
            toast(f"Error al abrir selector: {str(e)}")

    def _on_file_selected(self, selection):
        if selection and len(selection) > 0:
            self.selected_file = selection[0]
            file_name = os.path.basename(str(self.selected_file))
            Clock.schedule_once(lambda dt: setattr(
                self.screen.ids.file_label, 'text', f"Archivo: {file_name}"))
            toast("Archivo seleccionado")

            # Si ya estamos conectados, habilitar envío
            if self.connected and self.is_client:
                self.screen.ids.btn_send.disabled = False

    # -------------------------------------------------------------------------
    # ENVÍO DE ARCHIVO (Cliente)
    # -------------------------------------------------------------------------
    def start_sending(self):
        """Inicia el envío del archivo en un hilo separado"""
        if not self.connected:
            toast("No hay conexión")
            return

        if not self.selected_file:
            toast("Selecciona un archivo primero")
            return

        if not self.client_socket:
            toast("Socket no disponible")
            return

        self.update_status("Enviando archivo...")
        self.screen.ids.btn_send.disabled = True
        threading.Thread(target=self._send_file_thread, daemon=True).start()

    def _send_file_thread(self):
        """Hilo que envía el archivo por el OutputStream"""
        try:
            output_stream = self.client_socket.getOutputStream()
            file_size = os.path.getsize(self.selected_file)
            sent_bytes = 0

            with open(self.selected_file, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    output_stream.write(chunk)
                    output_stream.flush()
                    sent_bytes += len(chunk)
                    # Actualizar progreso (opcional)
                    if sent_bytes % (CHUNK_SIZE * 100) == 0:
                        print(f"Enviados {sent_bytes}/{file_size} bytes")

            Clock.schedule_once(lambda dt: self._on_send_complete())

        except Exception as e:
            error_msg = f"Error al enviar: {str(e)}"
            Clock.schedule_once(lambda dt: toast(error_msg))
            traceback.print_exc()
            Clock.schedule_once(lambda dt: setattr(self.screen.ids.btn_send, 'disabled', False))

    def _on_send_complete(self):
        """Se llama cuando el envío termina correctamente"""
        self.update_status("Archivo enviado con éxito")
        toast("¡Envío completado!")
        self.screen.ids.btn_send.disabled = False

    # -------------------------------------------------------------------------
    # RECEPCIÓN DE ARCHIVO (Solo para el servidor)
    # -------------------------------------------------------------------------
    def _receive_file_thread(self):
        """Hilo que escucha datos entrantes (para servidor)"""
        if not self.client_socket:
            return

        try:
            input_stream = self.client_socket.getInputStream()
            buffer = bytearray(CHUNK_SIZE)

            # Determinar ruta de guardado (directorio de Descargas)
            # Usamos getExternalFilesDir para no requerir permisos extra
            if platform == 'android':
                from android.os import Environment
                from jnius import autoclass
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                context = PythonActivity.mActivity
                # Directorio privado de la app en almacenamiento externo
                files_dir = context.getExternalFilesDir(None).getAbsolutePath()
                # Si prefieres Descargas (requiere permiso WRITE_EXTERNAL_STORAGE), usa:
                # downloads_path = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).getAbsolutePath()
                # received_file_path = os.path.join(downloads_path, f"recibido_{timestamp}.bin")
            else:
                files_dir = "."  # directorio actual en PC

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            received_file_path = os.path.join(files_dir, f"recibido_{timestamp}.bin")

            with open(received_file_path, "wb") as f:
                while True:
                    bytes_read = input_stream.read(buffer)
                    if bytes_read <= 0:
                        break
                    f.write(buffer[:bytes_read])

            Clock.schedule_once(lambda dt: self._on_receive_complete(received_file_path))

        except Exception as e:
            print(f"Error en recepción: {str(e)}")
            traceback.print_exc()

    def _on_receive_complete(self, file_path):
        """Se llama cuando se recibe un archivo completamente"""
        file_name = os.path.basename(file_path)
        self.update_status(f"Archivo recibido: {file_name}")
        toast(f"Archivo guardado en {file_name}")
        # Podrías abrir el archivo con un Intent aquí

# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================
if __name__ == '__main__':
    AplicacionBluetoothDirecto().run()

# adapters/telegram/client.py
"""
Wrapper del cliente de Telegram (Telethon).
Simplifica la configuración y manejo de eventos.

ACTUALIZADO: Soporte para QR Code login
"""
from __future__ import annotations

import traceback
from typing import Callable, Optional

from telethon import TelegramClient, events
from infrastructure.logging import get_logger

from core.utils import set_tg_startup_cutoff, should_process_tg_message, safe_text_sample
from core.state import BotState


class TelegramBotClient:
    """
    Wrapper del cliente de Telegram.
    
    Simplifica:
    - Conexión y autenticación (con QR Code opcional)
    - Configuración de handlers
    - Logging de eventos
    - Filtrado de mensajes (startup cutoff)
    """
    
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_name: str,
        channel_id: int,
        state: BotState,
        use_qr: bool = False,
    ):
        """
        Args:
            api_id: API ID de Telegram
            api_hash: API Hash de Telegram
            session_name: Nombre de la sesión
            channel_id: ID del canal a monitorear
            state: Estado del bot
            use_qr: Si True, intenta login con QR code
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.channel_id = channel_id
        self.state = state
        self.use_qr = use_qr
        self.logger = get_logger()
        
        self.client = TelegramClient(session_name, api_id, api_hash)
        self._on_message_callback: Optional[Callable] = None
        self._on_edit_callback: Optional[Callable] = None
    
    async def start(self) -> bool:
        """
        Inicia el cliente de Telegram.
        
        Si use_qr=True, intenta login con QR code.
        Si use_qr=False, usa el método normal (teléfono/código).
        
        Returns:
            True si la conexión fue exitosa
        """
        try:
            if self.use_qr:
                await self._start_with_qr()
            else:
                await self.client.start()
            
            user_id = getattr(self.client, "_self_id", "unknown")
            self.logger.event(
                "TG_READY",
                user_id=str(user_id),
                channel_id=self.channel_id,
            )
            
            # Set startup cutoff para evitar backlog
            cutoff_iso = set_tg_startup_cutoff(self.state)
            self.logger.event(
                "TG_STARTUP_CUTOFF_SET",
                cutoff=cutoff_iso,
            )
            
            return True
            
        except Exception as ex:
            self.logger.error(
                "Error iniciando Telegram client",
                exc_info=True,
                error=str(ex),
            )
            return False
    
    async def _start_with_qr(self) -> None:
        """
        Inicia sesión usando QR code.
        
        Genera un QR code como imagen PNG que el usuario escanea
        desde su app de Telegram.
        """
        import qrcode
        from io import BytesIO
        from PIL import Image
        
        await self.client.connect()
        
        if await self.client.is_user_authorized():
            self.logger.info("Ya está autorizado, usando sesión existente")
            return
        
        print("\n" + "="*60)
        print("🔐 TELEGRAM LOGIN CON QR CODE")
        print("="*60)
        print("\nGenerando QR code...")
        
        # Solicitar QR code a Telegram
        qr_login = await self.client.qr_login()
        
        # Guardar imagen del QR
        qr_image_path = "telegram_qr.png"
        
        # Generar QR code como imagen
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_login.url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(qr_image_path)
        
        print(f"\n✅ QR Code guardado en: {qr_image_path}")
        print("\n📱 INSTRUCCIONES:")
        print("1. Abre Telegram en tu teléfono")
        print("2. Ve a Settings → Devices → Link Desktop Device")
        print("3. Escanea el QR code de la imagen 'telegram_qr.png'")
        print("\n⏳ Esperando que escanees el QR code...\n")
        
        # También mostrar en consola (ASCII art)
        qr_console = qrcode.QRCode()
        qr_console.add_data(qr_login.url)
        qr_console.make()
        qr_console.print_ascii()
        
        # Esperar a que el usuario escanee
        try:
            await qr_login.wait(timeout=120)  # 2 minutos timeout
            print("\n✅ Login exitoso!")
        except TimeoutError:
            print("\n❌ Timeout: No escaneaste el QR a tiempo")
            raise
    
    def setup_handlers(
        self,
        on_message: Callable,
        on_edit: Callable,
    ) -> None:
        """
        Configura los handlers de mensajes.
        
        Args:
            on_message: Callback para mensajes nuevos
            on_edit: Callback para mensajes editados
        """
        self._on_message_callback = on_message
        self._on_edit_callback = on_edit
        
        # Handler de mensajes nuevos
        @self.client.on(events.NewMessage(chats=self.channel_id))
        async def handle_new_message(event):
            await self._handle_message(event, is_edit=False)
        
        # Handler de mensajes editados
        @self.client.on(events.MessageEdited(chats=self.channel_id))
        async def handle_edited_message(event):
            await self._handle_message(event, is_edit=True)
        
        self.logger.info(
            "Handlers configurados",
            channel_id=self.channel_id,
        )
    
    async def run(self) -> None:
        """Ejecuta el cliente hasta que se desconecte."""
        await self.client.run_until_disconnected()
    
    async def disconnect(self) -> None:
        """Desconecta el cliente."""
        await self.client.disconnect()
        self.logger.info("Telegram client desconectado")
    
    # ==========================================
    # Métodos Privados
    # ==========================================
    
    async def _handle_message(self, event, is_edit: bool) -> None:
        """
        Procesa un mensaje o edición.
        
        Args:
            event: Evento de Telethon
            is_edit: Si es una edición de mensaje
        """
        try:
            msg = event.message
            text = msg.message or ""
            reply_to = msg.reply_to_msg_id if msg.reply_to else None
            msg_date_iso = msg.date.isoformat() if msg.date else None
            
            # Verificar si debemos procesar
            ok, reason, cutoff_iso, age_s = should_process_tg_message(
                state=self.state,
                msg_id=msg.id,
                msg_date_iso=msg_date_iso,
                is_edit=is_edit,
            )
            
            if not ok:
                self.logger.event(
                    "TG_MESSAGE_IGNORED",
                    msg_id=msg.id,
                    is_edit=is_edit,
                    reply_to=reply_to,
                    date=msg_date_iso,
                    cutoff=cutoff_iso,
                    age_s=age_s,
                    reason=reason,
                    text=safe_text_sample(text, 300),
                )
                return
            
            # Loggear mensaje
            event_type = "TG_MESSAGE_EDITED" if is_edit else "TG_MESSAGE"
            self.logger.event(
                event_type,
                msg_id=msg.id,
                reply_to=reply_to,
                date=msg_date_iso,
                text=text,
            )
            
            # Ejecutar callback apropiado
            callback = self._on_edit_callback if is_edit else self._on_message_callback
            if callback:
                await callback(
                    msg_id=msg.id,
                    text=text,
                    reply_to=reply_to,
                    date_iso=msg_date_iso,
                    is_edit=is_edit,
                )
        
        except Exception as ex:
            event_type = "TG_EDIT_HANDLER_ERROR" if is_edit else "TG_HANDLER_ERROR"
            self.logger.event(
                event_type,
                error=str(ex),
                traceback=traceback.format_exc(),
            )
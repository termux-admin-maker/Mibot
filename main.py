import sqlite3
import logging
import io
import os
import asyncio
import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# ==========================================
# CONFIGURACIÓN DE LOGS
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 1. CONFIGURACIÓN GLOBAL Y ENTORNO
# ==========================================
TOKEN "8975822686:AAEX1ZLjBf21tOet3j95Sp4tRV5b8PuO84E"
ADMIN_ID = 8637165051

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "CHEAT.db")

# Estados de Conversación (Actualizados con BUSCAR_KEY_ADM)
(CREAR_PAQUETE_PROJ, CREAR_PAQUETE_PROD, CREAR_PAQUETE_DUR, ADD_PROD_NAME, ADD_PROD_DUR, ADD_DUR_DUR,
 DAR_SALDO, COM_TEXT, COM_PHOTO, COM_BTN, EDIT_PRECIO, OFERTA_PRECIO, ADD_KEYS, EDIT_SOPORTE, EDIT_CANAL,
 EDIT_BANNER, EDIT_METODOS, CANJEAR_CUPON, ENVIAR_COMPROBANTE, APROBAR_RECARGA, CREAR_CUPON_COD,
 CREAR_CUPON_VAL, CREAR_CUPON_LIM, BORRAR_USER, ADD_LINK_DESC, ADD_LINK_TUT, RENOMBRAR_PROD, BUSCAR_USER,
 ADD_PAIS_NOM, ADD_PAIS_DATOS, EDIT_PAIS_TASA, REEMPLAZAR_KEY, CFG_DESC_SOCIO, CFG_COM_REF, CAMBIAR_RANGO,
 EDIT_IMG_REG, EDIT_IMG_PJ, EDIT_IMG_PD, EDIT_PAIS_DET, EDIT_PRECIO_SOCIEDAD, ENVIAR_COMP_SOCIEDAD, CUSTOM_QTY, CUSTOM_RECARGA, BUSCAR_KEY_ADM) = range(44)

# NUEVOS ESTADOS PARA RED DE SOCIOS
(RED_BUSCAR_SOCIO,) = range(44, 45)

def inicializar_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # OPTIMIZACIÓN DE ALTO RENDIMIENTO (Manejo de Tráfico Masivo)
        c.execute('PRAGMA journal_mode=WAL;')
        c.execute('PRAGMA synchronous=NORMAL;')

        c.execute('''CREATE TABLE IF NOT EXISTS usuarios (user_id INTEGER PRIMARY KEY, telefono TEXT, username TEXT, saldo REAL DEFAULT 0.0, rango TEXT DEFAULT 'cliente', referido_por INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS proyectos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, imagen TEXT DEFAULT '')''')
        c.execute('''CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY AUTOINCREMENT, proyecto_id INTEGER, nombre TEXT, link_descarga TEXT, link_tutorial TEXT, imagen TEXT DEFAULT '')''')
        c.execute('''CREATE TABLE IF NOT EXISTS duraciones (id INTEGER PRIMARY KEY AUTOINCREMENT, producto_id INTEGER, dias INTEGER, precio REAL, precio_socio REAL DEFAULT 0.0, precio_oferta REAL DEFAULT 0.0, en_oferta INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS keys (id INTEGER PRIMARY KEY AUTOINCREMENT, duracion_id INTEGER, llave TEXT, vendida INTEGER DEFAULT 0, comprador_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS config (clave TEXT PRIMARY KEY, valor TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS cupones (codigo TEXT PRIMARY KEY, valor REAL, limite INTEGER, usados INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS cupones_usados (codigo TEXT, user_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS metodos_pais (pais TEXT PRIMARY KEY, bandera TEXT, moneda TEXT, tasa REAL DEFAULT 1.0, detalles TEXT)''')

        # NUEVAS TABLAS PARA HISTORIALES Y GESTIÓN
        c.execute('''CREATE TABLE IF NOT EXISTS historial_recargas (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, monto REAL, moneda TEXT, pais TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS recargas_pendientes (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, monto REAL, pais TEXT, moneda TEXT)''')

        for table, col, default in [('proyectos', 'imagen', "''"), ('productos', 'imagen', "''"), ('duraciones', 'precio_socio', "0.0")]:
            try: c.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}")
            except sqlite3.OperationalError: pass

        try: c.execute("ALTER TABLE usuarios ADD COLUMN is_banned INTEGER DEFAULT 0")
        except sqlite3.OperationalError: pass

        try: c.execute("ALTER TABLE usuarios ADD COLUMN total_gastado REAL DEFAULT 0.0")
        except sqlite3.OperationalError: pass

        try: c.execute("ALTER TABLE keys ADD COLUMN fecha_compra TIMESTAMP")
        except sqlite3.OperationalError: pass

        c.execute("SELECT count(*) FROM metodos_pais")
        if c.fetchone()[0] == 0:
            default_paises = [
                ('México', '🇲🇽', 'MXN', 17.0, 'Transferencia SPEI a: 1234567890\nConcepto: Tu Usuario'),
                ('EE.UU', '🇺🇸', 'USD', 1.0, 'Pago por Zelle a: email@usa.com'),
                ('Venezuela', '🇻🇪', 'VES', 36.5, 'Pago Móvil: 0414-1234567, Banco\nConcepto: Pago de compras'),
                ('Colombia', '🇨🇴', 'COP', 3900.0, 'Nequi a: 3001234567')
            ]
            c.executemany("INSERT INTO metodos_pais VALUES (?, ?, ?, ?, ?)", default_paises)

        defaults = [
            ('link_soporte', 'https://t.me/SoporteBot'), ('link_canal', 'https://t.me/canal'),
            ('banner_url', ''), ('imagen_registro', ''), ('link_recargas', 'https://t.me/RecargasBot'),
            ('desc_socio', '20.0'), ('comision_ref', '5.0'), ('precio_sociedad', '50.0')
        ]
        c.executemany("INSERT OR IGNORE INTO config (clave, valor) VALUES (?, ?)", defaults)
        
        # NUEVAS TABLAS PARA EL SISTEMA DE SOCIOS Y GANANCIAS
        c.execute('''CREATE TABLE IF NOT EXISTS config_red (clave TEXT PRIMARY KEY, valor TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS red_socios (user_id INTEGER PRIMARY KEY, invitado_por INTEGER, nivel_red INTEGER, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS recargas_etiquetadas (id_recarga INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, vendedor_id INTEGER, vendedor_nombre TEXT, monto REAL, moneda TEXT, pais TEXT, metodo TEXT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        
        # VALORES POR DEFECTO DEL SISTEMA DE SOCIOS
        defaults_red = [('sistema_activo', '1'), ('texto_explicativo', '🤝 SISTEMA DE SOCIOS Y GANANCIAS\n═══════════════════════\n✅ Al publicar el Bot en tu canal:\n👉 Cuando alguien recargue saldo por tu parte, tú también ganas\n👉 Ejemplo: si tu socio recarga 5 USD → se le agrega a él y tú recibes lo mismo\n📌 ¿Cómo vendes tú?\n1. Usa los métodos de pago que trae el Bot\n2. Cuando te compren (ej: 3 USD Venezuela):\n   • Entra al Bot\n   • Selecciona el país correspondiente\n   • Elige ✍️ cantidad personalizada y pon el monto\n⚠️ IMPORTANTE:\nToda recarga que haga cualquiera que entró por tu enlace, llega al administrador ETIQUETADA CON TU NOMBRE Y TU ID. Al revisar y aprobar el comprobante, el administrador verá claramente «Traído por: TÚ», y te abonará tu ganancia directamente a saldo.\n🔗 TU ENLACE PARA COMPARTIR: `ENLACE`\n═══════════════════════')]
        c.executemany("INSERT OR IGNORE INTO config_red (clave, valor) VALUES (?, ?)", defaults_red)
        
        conn.commit()

def db_query(query, params=(), fetch=False, fetchall=False, commit=True):
    try:
        with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(query, params)
            if fetch:
                res = c.fetchone()
                return dict(res) if res else None
            if fetchall:
                res = c.fetchall()
                return [dict(row) for row in res] if res else []
            if commit:
                conn.commit()
            return None
    except sqlite3.Error as e:
        logger.error(f"Error BD ejecutando {query}: {e}")
        return [] if fetchall else None

def get_config(clave):
    res = db_query("SELECT valor FROM config WHERE clave = ?", (clave,), fetch=True)
    return res['valor'] if res else ""

def get_config_float(clave, default=0.0):
    val = get_config(clave)
    try:
        return float(val) if val else default
    except ValueError:
        return default

def md_safe(text):
    if not text: return ""
    return str(text).replace('_', ' ').replace('*', '').replace('`', "'").replace('[', '').replace(']', '')

def crear_paginacion(pagina, total, limite, prefijo_cb):
    botones = []
    if pagina > 0:
        botones.append(InlineKeyboardButton("⬅️ Anterior", callback_data=f"{prefijo_cb}_{pagina - 1}"))
    if (pagina + 1) * limite < total:
        botones.append(InlineKeyboardButton("Siguiente ➡️", callback_data=f"{prefijo_cb}_{pagina + 1}"))
    return [botones] if botones else []

def marcar_ocupado(context, estado=True):
    context.user_data['ocupado'] = estado

def esta_ocupado(context):
    return context.user_data.get('ocupado', False)

def usuario_baneado(user_id):
    res = db_query("SELECT is_banned FROM usuarios WHERE user_id = ?", (user_id,), fetch=True)
    return res and res.get('is_banned', 0) == 1

# ==========================================
# MOTOR DE VIGENCIA DE KEYS
# ==========================================
def calcular_tiempo_restante(fecha_str, dias_duracion):
    if not fecha_str: return "Desconocido (Sin fecha)"
    try:
        if '.' in fecha_str: fecha_str = fecha_str.split('.')[0]
        fecha_compra = datetime.datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
        fecha_expiracion = fecha_compra + datetime.timedelta(days=dias_duracion)
        ahora = datetime.datetime.utcnow()
        restante = fecha_expiracion - ahora

        if restante.total_seconds() <= 0: return "🔴 VENCIDA"

        dias = restante.days
        horas, remainder = divmod(restante.seconds, 3600)
        minutos, _ = divmod(remainder, 60)

        res = []
        if dias > 0: res.append(f"{dias}d")
        if horas > 0: res.append(f"{horas}h")
        if minutos > 0: res.append(f"{minutos}m")
        if not res: return "< 1m"
        return " ".join(res)
    except Exception:
        return "Error al calcular"

# ==========================================
# RUTINA DE DIFUSIÓN EN SEGUNDO PLANO
# ==========================================
async def broadcast_background(context: ContextTypes.DEFAULT_TYPE, mensaje: str):
    users = db_query("SELECT user_id FROM usuarios", fetchall=True)
    if not users: return
    for u in users:
        try:
            await context.bot.send_message(chat_id=u['user_id'], text=mensaje, parse_mode='Markdown')
        except: pass
        await asyncio.sleep(0.05)

# ==========================================
# MOTOR DE EDICIÓN FLUIDA (IN-PLACE)
# ==========================================
async def render_msg(query, context, texto, teclado, photo=None):
    message = query.message
    has_photo_new = bool(photo and photo != '0' and str(photo).strip() != '')
    has_photo_old = bool(message.photo or message.document)

    try:
        if has_photo_new and has_photo_old:
            await query.edit_message_media(media=InputMediaPhoto(media=photo, caption=texto, parse_mode='Markdown'), reply_markup=teclado)
        elif not has_photo_new and not has_photo_old:
            await query.edit_message_text(text=texto, reply_markup=teclado, parse_mode='Markdown')
        else:
            try: await message.delete()
            except: pass
            if has_photo_new:
                return await context.bot.send_photo(chat_id=message.chat_id, photo=photo, caption=texto, reply_markup=teclado, parse_mode='Markdown')
            else:
                return await context.bot.send_message(chat_id=message.chat_id, text=texto, reply_markup=teclado, parse_mode='Markdown')
        return message
    except Exception as e:
        logger.warning(f"Mensaje no modificado visualmente: {e}")
        return message

async def update_form(update, context, texto, teclado):
    try: await update.message.delete()
    except: pass
    prompt_id = context.user_data.get('prompt_msg_id')
    edit_success = False

    if prompt_id:
        try:
            await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=prompt_id, text=texto, reply_markup=teclado, parse_mode='Markdown')
            edit_success = True
        except Exception:
            try:
                await context.bot.edit_message_caption(chat_id=update.effective_chat.id, message_id=prompt_id, caption=texto, reply_markup=teclado, parse_mode='Markdown')
                edit_success = True
            except Exception as e:
                logger.warning(f"Error update_form editando: {e}")

    if not edit_success:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=texto, reply_markup=teclado, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error crítico en fallback de update_form: {e}")

def registrar_recarga_etiquetada(user_id, monto, moneda, pais, metodo):
    try:
        config = db_query("SELECT valor FROM config_red WHERE clave = 'sistema_activo'", fetch=True)
        if not config or config['valor'] != '1': return None

        vendedor = db_query("SELECT r.invitado_por, u.username FROM red_socios r JOIN usuarios u ON r.invitado_por = u.user_id WHERE r.user_id = ?", (user_id,), fetch=True)
        
        vendedor_id = vendedor['invitado_por'] if vendedor else 0
        vendedor_nombre = vendedor['username'] if (vendedor and vendedor['username']) else "SIN VENDEDOR / DIRECTO"

        db_query("INSERT INTO recargas_etiquetadas (user_id, vendedor_id, vendedor_nombre, monto, moneda, pais, metodo) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                 (user_id, vendedor_id, vendedor_nombre, monto, moneda, pais, metodo))

        if vendedor_id > 0:
            return f"\n🧑‍💼 **VENDEDOR ASOCIADO:** {md_safe(vendedor_nombre)} | `{vendedor_id}` | [Abrir Chat](tg://user?id={vendedor_id})"
        return "\n🧑‍💼 **VENDEDOR ASOCIADO:** SIN VENDEDOR / DIRECTO"
    except Exception as e:
        logger.error(f"Error en etiquetado: {e}")
        return ""

# ==========================================
# FLUJO PRINCIPAL Y CLIENTE (REGISTRO UNIVERSAL)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if usuario_baneado(user.id): return

    marcar_ocupado(context, False)
    context.user_data.clear()

    ref_id = 0
    if context.args and context.args[0].isdigit():
        ref_id = int(context.args[0])
    context.user_data['ref_tmp'] = ref_id

    if not db_query("SELECT * FROM usuarios WHERE user_id = ?", (user.id,), fetch=True):
        nombre_seguro = user.username if user.username else (user.first_name if user.first_name else "Usuario")
        db_query("INSERT OR IGNORE INTO usuarios (user_id, telefono, username, saldo, rango, referido_por, is_banned, total_gastado) VALUES (?, 'No_Proporcionado', ?, 0.0, 'cliente', ?, 0, 0.0)", (user.id, nombre_seguro, ref_id))

        # GUARDAR RELACIÓN EN LA RED DE SOCIOS PARA SIEMPRE
        if ref_id > 0 and ref_id != user.id:
            socio_existente = db_query("SELECT * FROM red_socios WHERE user_id = ?", (user.id,), fetch=True)
            if not socio_existente:
                ref_info = db_query("SELECT nivel_red FROM red_socios WHERE user_id = ?", (ref_id,), fetch=True)
                nivel = (ref_info['nivel_red'] + 1) if ref_info else 1
                db_query("INSERT OR IGNORE INTO red_socios (user_id, invitado_por, nivel_red) VALUES (?, ?, ?)", (user.id, ref_id, nivel))

        texto = f"👋 ¡Hola **{md_safe(user.first_name)}**!\n\nBienvenido a **LUIS MODZ OFC STORE BOT**.\nTu registro se ha completado automáticamente. 💬 Explora nuestro catálogo y descubre los mejores productos digitales al mejor precio."
        img_reg = get_config('imagen_registro')

        if img_reg and img_reg != '0':
            try: await context.bot.send_photo(chat_id=user.id, photo=img_reg, caption=texto, parse_mode='Markdown')
            except: await update.message.reply_text(texto, parse_mode='Markdown')
        else:
            await update.message.reply_text(texto, parse_mode='Markdown')

    await menu_principal(update, context)

async def recibir_contacto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if usuario_baneado(update.effective_user.id): return

    contacto = update.message.contact
    if contacto.user_id != update.effective_user.id:
        await update.message.reply_text("⚠️ Usa el botón oficial de Telegram para compartir tu contacto.")
        return

    db_query("UPDATE usuarios SET telefono = ? WHERE user_id = ?", (contacto.phone_number, update.effective_user.id))
    msg = await update.message.reply_text("✅ **¡Información actualizada con éxito!**", reply_markup=ReplyKeyboardRemove(), parse_mode='Markdown')
    try: await msg.delete()
    except: pass
    await menu_principal(update, context)

async def cancelar_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Acción cancelada.")
    marcar_ocupado(context, False)
    await menu_principal(update, context)
    return ConversationHandler.END

async def cancel_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)
    return ConversationHandler.END

async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.message else update.callback_query.from_user.id
    if usuario_baneado(user_id):
        if update.callback_query: await update.callback_query.answer("Acceso Denegado.", show_alert=True)
        return

    marcar_ocupado(context, False)
    user_data = db_query("SELECT * FROM usuarios WHERE user_id = ?", (user_id,), fetch=True)
    if not user_data: return

    rango_lbl = "😈 SOCIO" if user_data.get('rango') == 'socio' else "👤 Cliente"
    usr_name = md_safe(user_data.get('username') or 'Registrado')
    saldo_actual = user_data.get('saldo', 0.0)

    texto = f"**LUIS MODZ OFC STORE BOT**\n══════════════════\n{rango_lbl}: {usr_name}\n🆔 **ID de Cuenta:** `{user_id}`\n💰 **Saldo Disponible:** ${saldo_actual:.2f} USD\n══════════════════\nSelecciona una de las opciones del menú:"

    teclado = [
        [InlineKeyboardButton("🛒 COMPRÁR PRODUCTOS 🛍️", callback_data="c_proyectos_0")],
        [InlineKeyboardButton("💳 Recargar Saldo", callback_data="c_recargar"), InlineKeyboardButton("🎟️ Canjear Cupón", callback_data="c_cupon")],
        [InlineKeyboardButton("👤 Mi Perfil / Historial", callback_data="c_perfil_0")]
    ]

    if user_data.get('rango') == 'cliente':
        teclado.append([InlineKeyboardButton("🤝 Adquirir Sociedad (Revendedor 💰)", callback_data="c_info_sociedad")])

    teclado.append([InlineKeyboardButton("👨‍💻 Soporte Directo", url=get_config('link_soporte')), InlineKeyboardButton("📩 Canal Oficial", url=get_config('link_canal'))])

    if user_id == ADMIN_ID:
        teclado.append([InlineKeyboardButton("😈 PANEL ADMINISTRADOR 😈", callback_data="adm_panel")])

    markup = InlineKeyboardMarkup(teclado)
    banner = get_config('banner_url')

    if update.callback_query:
        await update.callback_query.answer()
        await render_msg(update.callback_query, context, texto, markup, banner)
    else:
        if banner and banner != '0':
            try: await context.bot.send_photo(chat_id=user_id, photo=banner, caption=texto, reply_markup=markup, parse_mode='Markdown')
            except: await context.bot.send_message(chat_id=user_id, text=texto, reply_markup=markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id=user_id, text=texto, reply_markup=markup, parse_mode='Markdown')

async def cliente_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if usuario_baneado(user_id):
        await query.answer("Tu cuenta está restringida.", show_alert=True)
        return

    if esta_ocupado(context):
        await query.answer("⚠️ Tienes una acción abierta. Cancela primero presionando el botón 'Cancelar Operación'.", show_alert=True)
        return

    await query.answer()
    data = query.data
    user_db = db_query("SELECT * FROM usuarios WHERE user_id = ?", (user_id,), fetch=True)

    if data == "c_info_sociedad":
        precio_sociedad = get_config_float('precio_sociedad', 50.0)
        desc_pct = get_config_float('desc_socio', 20.0)

        texto = (
            f"🤝 **SISTEMA DE ASOCIACIÓN** 🤝\n"
            f"══════════════════\n"
            f"¿Quieres iniciar tu propio negocio o simplemente obtener los mejores precios del mercado? Al convertirte en **Socio Oficial**, desbloquearás beneficios exclusivos:\n\n"
            f"✅ **Descuentos Automáticos:** Disfruta de un descuento generalizado (aprox {desc_pct}%) en todo nuestro catálogo.\n"
            f"✅ **Permiso de Reventa:** Estás autorizado para revender nuestros productos al precio que consideres justo.\n"
            f"✅ **Atención Prioritaria:** Soporte técnico enfocado en tus necesidades como distribuidor.\n\n"
            f"💰 **Inversión Única:** `${precio_sociedad:.2f} USD`\n\n"
            f"Elige el método por el cual deseas adquirir tu membresía:"
        )

        teclado = [
            [InlineKeyboardButton(f"💳 Pagar usando mi Saldo (${user_db.get('saldo', 0.0):.2f})", callback_data="c_socio_saldo")],
            [InlineKeyboardButton("🏦 Pagar con Depósito / Transferencia", callback_data="c_socio_transf")],
            [InlineKeyboardButton("⬅️ Regresar al Menú", callback_data="menu_principal")]
        ]
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data == "c_socio_saldo":
        precio_sociedad = get_config_float('precio_sociedad', 50.0)

        if user_db.get('saldo', 0.0) < precio_sociedad:
            await query.answer("❌ Saldo insuficiente para realizar esta operación.", show_alert=True)
            teclado_error = [[InlineKeyboardButton("💳 Ir a Recargar Saldo", callback_data="c_recargar")], [InlineKeyboardButton("⬅️ Volver atrás", callback_data="c_info_sociedad")]]
            await render_msg(query, context, f"❌ **FONDOS INSUFICIENTES**\n\nEl costo de la membresía es de **${precio_sociedad:.2f} USD**, pero tu saldo actual es de **${user_db.get('saldo', 0.0):.2f} USD**.", InlineKeyboardMarkup(teclado_error))
            return

        db_query("UPDATE usuarios SET saldo = saldo - ?, rango = 'socio', total_gastado = total_gastado + ? WHERE user_id = ?", (precio_sociedad, precio_sociedad, user_id))

        texto_exito = (
            f"🎉 **¡TRANSACCIÓN COMPLETADA!** 🎉\n"
            f"══════════════════\n"
            f"Tu cuenta ha sido ascendida de manera inmediata. A partir de este momento, eres oficialmente un **Socio VIP** 💎.\n\n"
            f"Ve a explorar el catálogo; notarás que todos los precios han sido reducidos exclusivamente para ti. ¡Mucho éxito en tus ventas!"
        )
        await render_msg(query, context, texto_exito, InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Ir a Comprar Productos", callback_data="c_proyectos_0")], [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal")]]))

    elif data == "c_socio_transf":
        paises = db_query("SELECT * FROM metodos_pais", fetchall=True)
        teclado = []
        fila = []
        for p in paises:
            fila.append(InlineKeyboardButton(f"{p['bandera']} {p['pais']}", callback_data=f"c_socp_{p['pais']}"))
            if len(fila) == 2:
                teclado.append(fila)
                fila = []
        if fila: teclado.append(fila)
        teclado.append([InlineKeyboardButton("⬅️ Cancelar y volver atrás", callback_data="c_info_sociedad")])
        await render_msg(query, context, "🌎 **PAGO DE MEMBRESÍA**\nSelecciona el país o método que utilizarás para depositar el pago:", InlineKeyboardMarkup(teclado))


    elif data.startswith("c_perfil_"):
        pagina = int(data.split("_")[2])
        limite = 5
        keys = db_query("SELECT k.llave, p.nombre, d.dias FROM keys k JOIN duraciones d ON k.duracion_id=d.id JOIN productos p ON d.producto_id=p.id WHERE k.comprador_id = ? ORDER BY k.id DESC LIMIT ? OFFSET ?", (user_id, limite, pagina * limite), fetchall=True)

        total_res = db_query("SELECT COUNT(*) as c FROM keys WHERE comprador_id = ?", (user_id,), fetch=True)
        total = total_res['c'] if total_res else 0

        ref_count_res = db_query("SELECT COUNT(*) as c FROM usuarios WHERE referido_por = ?", (user_id,), fetch=True)
        ref_count = ref_count_res['c'] if ref_count_res else 0

        link_ref = f"https://t.me/{context.bot.username}?start={user_id}"

        texto = (
            f"👤 **TU PERFIL Y AFILIADOS**\n"
            f"══════════════════\n"
            f"💰 **Saldo Disponible:** ${user_db.get('saldo', 0.0):.2f} USD\n"
            f"🔥 **Total Gastado:** ${user_db.get('total_gastado', 0.0):.2f} USD\n"
            f"👥 Has invitado a: **{ref_count} amigos**\n"
            f"🔗 Tu link de invitación es:\n`{link_ref}`\n"
            f"_(Ganas el {get_config_float('comision_ref', 5.0)}% de comisión por las compras de tus invitados)_\n"
            f"══════════════════\n"
            f"**TUS COMPRAS RECIENTES (Pág {pagina + 1}):**\n"
        )
        for k in keys: texto += f"📦 {md_safe(k['nombre'])} ({k['dias']}d) ➔ `{k['llave']}`\n"
        if not keys: texto += "_Aún no tienes historial de compras._"

        teclado = crear_paginacion(pagina, total, limite, "c_perfil")
        teclado.append([InlineKeyboardButton("⏱️ Ver Vigencia de Claves", callback_data="c_vigencia_0")])
        
        # NUEVO SISTEMA: BOTÓN RED DE SOCIOS AL FINAL DEL PERFIL
        if user_db.get('rango') == 'socio':
            teclado.append([InlineKeyboardButton("💎 MI RED DE SOCIOS Y GANANCIAS", callback_data="c_red_inicio")])
            
        teclado.append([InlineKeyboardButton("⬅️ Volver al Menú Principal", callback_data="menu_principal")])
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data.startswith("c_vigencia_"):
        pagina = int(data.split("_")[2])
        limite = 5
        keys = db_query("SELECT k.llave, p.nombre, d.dias, k.fecha_compra FROM keys k JOIN duraciones d ON k.duracion_id=d.id JOIN productos p ON d.producto_id=p.id WHERE k.comprador_id = ? AND k.vendida = 1 AND k.fecha_compra IS NOT NULL ORDER BY k.fecha_compra DESC LIMIT ? OFFSET ?", (user_id, limite, pagina * limite), fetchall=True)

        total_res = db_query("SELECT COUNT(*) as c FROM keys WHERE comprador_id = ? AND vendida = 1 AND fecha_compra IS NOT NULL", (user_id,), fetch=True)
        total = total_res['c'] if total_res else 0

        texto = f"⏱️ **VIGENCIA DE TUS CLAVES (Pág {pagina + 1})**\n══════════════════\n_Calculado según la fecha y hora exacta de tu compra_\n\n"

        for k in keys:
            restante = calcular_tiempo_restante(k['fecha_compra'], k['dias'])
            texto += f"📦 **{md_safe(k['nombre'])}** ({k['dias']}d)\n🔑 `{k['llave']}`\n⏳ Restante: **{restante}**\n\n"

        if not keys:
            texto += "_Aún no tienes licencias activas para mostrar._\n"

        teclado = crear_paginacion(pagina, total, limite, "c_vigencia")
        teclado.append([InlineKeyboardButton("⬅️ Volver a Mi Perfil", callback_data="c_perfil_0")])
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data == "c_recargar":
        paises = db_query("SELECT * FROM metodos_pais", fetchall=True)
        teclado = []
        fila = []
        for p in paises:
            fila.append(InlineKeyboardButton(f"{p['bandera']} {p['pais']}", callback_data=f"c_recp_{p['pais']}"))
            if len(fila) == 2:
                teclado.append(fila)
                fila = []
        if fila: teclado.append(fila)
        teclado.append([InlineKeyboardButton("📲 Contactar para Recarga (Asistida)", url=get_config('link_recargas'))])
        teclado.append([InlineKeyboardButton("❌ Cancelar", callback_data="menu_principal")])
        await render_msg(query, context, "🌎 **SELECCIONA TU MÉTODO O PAÍS PARA RECARGAR:**", InlineKeyboardMarkup(teclado))

    elif data.startswith("c_recp_"):
        pais = data.split("_", 2)[2]
        montos = [5, 10, 15, 20, 30, 50, 100]
        teclado = []
        fila = []
        for m in montos:
            fila.append(InlineKeyboardButton(f"${m} USD", callback_data=f"c_recm_{pais}_{m}"))
            if len(fila) == 3:
                teclado.append(fila)
                fila = []
        if fila: teclado.append(fila)

        # Nueva opción de monto personalizado
        teclado.append([InlineKeyboardButton("✍️ Monto Personalizado", callback_data=f"c_reccustom_{pais}")])
        teclado.append([InlineKeyboardButton("⬅️ Elegir otro país", callback_data="c_recargar")])
        await render_msg(query, context, f"💵 **{pais} - SELECCIONA EL MONTO DE SALDO QUE DESEAS:**", InlineKeyboardMarkup(teclado))

    elif data.startswith("c_proyectos_"):
        pagina = int(data.split("_")[2])
        limite = 5
        proyectos = db_query("SELECT * FROM proyectos ORDER BY id DESC LIMIT ? OFFSET ?", (limite, pagina * limite), fetchall=True)

        total_res = db_query("SELECT COUNT(*) as c FROM proyectos", fetch=True)
        total = total_res['c'] if total_res else 0

        teclado = [[InlineKeyboardButton(f"📂 {md_safe(p['nombre'])}", callback_data=f"c_pj_{p['id']}_0")] for p in proyectos]
        teclado.extend(crear_paginacion(pagina, total, limite, "c_proyectos"))
        teclado.append([InlineKeyboardButton("⬅️ Regresar al Inicio", callback_data="menu_principal")])
        await render_msg(query, context, "🛒 **CATEGORÍAS DISPONIBLES 🟣**\nPor favor, selecciona la categoría de tu interés:", InlineKeyboardMarkup(teclado), get_config('banner_url'))

    elif data.startswith("c_pj_"):
        _, _, pid, pagina = data.split("_")
        pagina = int(pagina)
        limite = 5
        pj = db_query("SELECT * FROM proyectos WHERE id = ?", (pid,), fetch=True)
        productos = db_query("SELECT * FROM productos WHERE proyecto_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (pid, limite, pagina * limite), fetchall=True)

        total_res = db_query("SELECT COUNT(*) as c FROM productos WHERE proyecto_id = ?", (pid,), fetch=True)
        total = total_res['c'] if total_res else 0

        teclado = [[InlineKeyboardButton(f"📦 {md_safe(p['nombre'])}", callback_data=f"c_pd_{p['id']}")] for p in productos]
        teclado.extend(crear_paginacion(pagina, total, limite, f"c_pj_{pid}"))
        teclado.append([InlineKeyboardButton("⬅️ Volver a las Categorías", callback_data="c_proyectos_0")])
        texto = f"📂 **{md_safe(pj.get('nombre', 'Categoría'))}**\n\n📦 **PRODUCTOS DISPONIBLES 🔥**\nSelecciona el artículo específico que deseas revisar:"
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado), pj.get('imagen'))

    elif data.startswith("c_pd_"):
        pdid = data.split("_")[2]
        pd = db_query("SELECT * FROM productos WHERE id = ?", (pdid,), fetch=True)
        duraciones = db_query("SELECT * FROM duraciones WHERE producto_id = ?", (pdid,), fetchall=True)
        teclado = []
        es_socio = (user_db.get('rango') == 'socio')
        desc_pct = get_config_float('desc_socio', 0.0)

        for d in duraciones:
            precio_base = d['precio_socio'] if (es_socio and d['precio_socio'] > 0) else (d['precio'] * (1 - desc_pct/100) if es_socio else d['precio'])
            if d['en_oferta'] and d['precio_oferta'] < precio_base:
                precio_f = d['precio_oferta']
                lbl = "🔥 OFERTA: "
            else:
                precio_f = precio_base
                lbl = " 🟢 SOCIO: " if es_socio else ""
            teclado.append([InlineKeyboardButton(f"⏳ {d['dias']} Días | {lbl}${precio_f:.2f}", callback_data=f"c_qty_{d['id']}_{precio_f}")])

        teclado.append([InlineKeyboardButton("⬅️ Volver a Productos", callback_data=f"c_pj_{pd.get('proyecto_id')}_0")])
        txt_h = f"📦 **{md_safe(pd.get('nombre'))}**\n\n⏱️ **SELECCIONA LA DURACIÓN DE TU LICENCIA**:\n_(Como Socio 🟢, estás visualizando tus precios exclusivos)_" if es_socio else f"📦 **{md_safe(pd.get('nombre'))}**\n\n⏱️ **SELECCIONA LA DURACIÓN DE TU LICENCIA**:"
        await render_msg(query, context, txt_h, InlineKeyboardMarkup(teclado), pd.get('imagen'))

    elif data.startswith("c_qty_"):
        _, _, dur_id, precio = data.split("_")

        stock_res = db_query("SELECT COUNT(*) as c FROM keys WHERE duracion_id = ? AND vendida = 0", (dur_id,), fetch=True)
        stock = stock_res['c'] if stock_res else 0

        if stock <= 0:
            await query.answer("❌ Lo sentimos, el producto está sin stock por el momento.", show_alert=True)
            return

        fila1 = []
        fila2 = []
        if stock >= 1: fila1.append(InlineKeyboardButton("1 Licencia", callback_data=f"c_conf_{dur_id}_{precio}_1"))
        if stock >= 2: fila1.append(InlineKeyboardButton("2 Licencias", callback_data=f"c_conf_{dur_id}_{precio}_2"))
        if stock >= 5: fila2.append(InlineKeyboardButton("5 Licencias", callback_data=f"c_conf_{dur_id}_{precio}_5"))
        if stock >= 10: fila2.append(InlineKeyboardButton("10 Licencias", callback_data=f"c_conf_{dur_id}_{precio}_10"))

        teclado = []
        if fila1: teclado.append(fila1)
        if fila2: teclado.append(fila2)

        # Opción extra: cantidad libre
        if stock >= 1:
            teclado.append([InlineKeyboardButton("✍️ Elegir cantidad libre", callback_data=f"c_qtycustom_{dur_id}_{precio}")])

        d_info = db_query("SELECT d.producto_id, p.imagen FROM duraciones d JOIN productos p ON d.producto_id=p.id WHERE d.id = ?", (dur_id,), fetch=True)
        teclado.append([InlineKeyboardButton("⬅️ Volver a Opciones de Duración", callback_data=f"c_pd_{d_info.get('producto_id')}")])
        await render_msg(query, context, f"🛒 **¿Cuántas Licencias deseas comprar?**\nNuestro inventario se actualiza en tiempo real de manera encriptada.", InlineKeyboardMarkup(teclado), d_info.get('imagen'))

    elif data.startswith("c_conf_"):
        _, _, dur_id, precio, qty = data.split("_")
        precio = float(precio)
        qty = int(qty)
        total_pagar = precio * qty
        d_info = db_query("SELECT d.dias, p.nombre, p.imagen FROM duraciones d JOIN productos p ON d.producto_id=p.id WHERE d.id = ?", (dur_id,), fetch=True)

        if user_db.get('saldo', 0.0) < total_pagar:
            teclado = [[InlineKeyboardButton("💳 Ir a Recargar Saldo", callback_data="c_recargar")], [InlineKeyboardButton("⬅️ Cancelar y volver al Menú", callback_data="menu_principal")]]
            await render_msg(query, context, f"❌ **SALDO INSUFICIENTE**\n\nCosto total de la Orden: **${total_pagar:.2f} USD**\nTu saldo actual es de: **${user_db.get('saldo', 0.0):.2f} USD**", InlineKeyboardMarkup(teclado), d_info.get('imagen'))
            return

        restante = user_db.get('saldo', 0.0) - total_pagar
        resumen = f"⚠️ **RESUMEN DE TU COMPRA**\n══════════════════\n📦 Producto a entregar: **{md_safe(d_info.get('nombre'))}**\n⏱️ Vigencia de Licencia: **{d_info.get('dias')} Días**\n🔑 Unidades seleccionadas: **{qty} Licencia(s)**\n\n💰 Tu Saldo actual: **${user_db.get('saldo', 0.0):.2f} USD**\n📉 Tu Saldo tras la compra: **${restante:.2f} USD**\n\n¿Deseas confirmar y procesar esta transacción?"
        teclado = [[InlineKeyboardButton("✅ SÍ, CONFIRMAR Y PAGAR", callback_data=f"c_buy_{dur_id}_{precio}_{qty}")], [InlineKeyboardButton("❌ Cancelar Orden", callback_data="menu_principal")]]
        await render_msg(query, context, resumen, InlineKeyboardMarkup(teclado), d_info.get('imagen'))

    elif data.startswith("c_buy_"):
        _, _, dur_id, precio, qty = data.split("_")
        precio = float(precio)
        qty = int(qty)
        total_pagar = precio * qty

        try:
            with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()

                c.execute("SELECT saldo, referido_por FROM usuarios WHERE user_id = ?", (user_id,))
                user_actual = c.fetchone()

                if not user_actual or user_actual['saldo'] < total_pagar:
                    await query.answer("❌ Saldo insuficiente o modificado durante la petición.", show_alert=True)
                    return await menu_principal(update, context)

                c.execute("SELECT id, llave FROM keys WHERE duracion_id = ? AND vendida = 0 LIMIT ?", (dur_id, qty))
                keys_disp = c.fetchall()
                if len(keys_disp) < qty:
                    await render_msg(query, context, "❌ El stock cambió antes de poder confirmar tu pago. Intenta nuevamente.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu_principal")]]))
                    return

                # ACTUALIZAMOS SALDO Y REGISTRAMOS EL GASTO TOTAL DEL USUARIO
                c.execute("UPDATE usuarios SET saldo = saldo - ?, total_gastado = total_gastado + ? WHERE user_id = ?", (total_pagar, total_pagar, user_id))
                keys_list_str = ""
                for k in keys_disp:
                    # REGISTRAMOS LA FECHA DE ENTREGA DE LA KEY PARA VIGENCIA EXACTA EN UTC
                    c.execute("UPDATE keys SET vendida = 1, comprador_id = ?, fecha_compra = CURRENT_TIMESTAMP WHERE id = ?", (user_id, k['id']))
                    keys_list_str += f"{k['llave']}\n"

                ref_id = user_actual['referido_por']
                comision = 0.0
                if ref_id > 0:
                    c.execute("SELECT valor FROM config WHERE clave = 'comision_ref'")
                    conf_ref = c.fetchone()
                    try:
                        pct_ref = float(conf_ref['valor']) if conf_ref and conf_ref['valor'] else 5.0
                    except ValueError:
                        pct_ref = 5.0

                    comision = total_pagar * (pct_ref / 100)
                    c.execute("UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?", (comision, ref_id))

                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error de Transacción de compra: {e}")
            await render_msg(query, context, "❌ Ocurrió un error inesperado al procesar. Por favor contacta a soporte.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menú Principal", callback_data="menu_principal")]]))
            return

        if ref_id > 0 and comision > 0:
            try: await context.bot.send_message(ref_id, f"🎉 **¡COMISIÓN ACREDITADA!**\nTu afiliado acaba de realizar una compra y has recibido **${comision:.2f} USD** en tu saldo virtual. ¡Sigue invitando!")
            except: pass

        d_info = db_query("SELECT d.dias, p.nombre, p.link_descarga, p.link_tutorial, p.imagen FROM duraciones d JOIN productos p ON d.producto_id=p.id WHERE d.id = ?", (dur_id,), fetch=True)

        stock_res = db_query("SELECT COUNT(*) as c FROM keys WHERE duracion_id = ? AND vendida = 0", (dur_id,), fetch=True)
        stock_restante = stock_res['c'] if stock_res else 0

        if stock_restante <= 3:
            try: await context.bot.send_message(ADMIN_ID, f"⚠️ **ALERTA DE INVENTARIO**\nEl producto **{md_safe(d_info.get('nombre'))}** está a punto de agotarse. Quedan {stock_restante} licencias disponibles en la base de datos.")
            except: pass

        texto_exito = f"✅ **COMPRA COMPLETADA CON ÉXITO** ✅\n══════════════════\n📦 **Producto Adquirido:** {md_safe(d_info.get('nombre'))}\n⏳ **Duración:** {d_info.get('dias')} días\n💳 **Saldo Restante:** ${(user_actual['saldo'] - total_pagar):.2f} USD\n══════════════════\n"
        teclado = []
        if d_info.get('link_descarga'):
            teclado.append(InlineKeyboardButton("📥 Enlace Oficial de Descarga", url=d_info['link_descarga']))
        if d_info.get('link_tutorial'):
            teclado.append(InlineKeyboardButton("📺 Ver Guía de Instalación", url=d_info['link_tutorial']))

        botones = [teclado] if teclado else []
        botones.append([InlineKeyboardButton("🏠 Regresar al Menú Principal", callback_data="menu_principal")])

        if qty > 5:
            texto_exito += "📂 **TUS LICENCIAS (KEYS):**\n_Por seguridad y comodidad al ser más de 5 licencias, se han adjuntado en un archivo de texto._"
            file = io.BytesIO(keys_list_str.encode('utf-8'))
            file.name = f"Tus_Licencias_{md_safe(d_info.get('nombre')).replace(' ', '_')}.txt"
            await context.bot.send_document(chat_id=user_id, document=file, caption=texto_exito, reply_markup=InlineKeyboardMarkup(botones), parse_mode='Markdown')
            try: await query.message.delete()
            except: pass
        else:
            claves_formateadas = "".join([f"🔑 `{k.strip()}`\n" for k in keys_list_str.strip().split('\n')])
            texto_exito += f"**TUS KEYS ({qty}):**\n{claves_formateadas}══════════════════\n_Toca cualquier credencial para copiarla automáticamente al portapapeles._"
            await render_msg(query, context, texto_exito, InlineKeyboardMarkup(botones), d_info.get('imagen'))

    elif data == "c_red_inicio":
        if user_db.get('rango') != 'socio': return

        config = db_query("SELECT valor FROM config_red WHERE clave = 'sistema_activo'", fetch=True)
        if not config or config['valor'] != '1':
            await render_msg(query, context, "⚙️ **SISTEMA EN MANTENIMIENTO**\nEl sistema de red de socios se encuentra temporalmente desactivado por la administración.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ VOLVER A MI PERFIL", callback_data="c_perfil_0")]]))
            return
            
        texto_db = db_query("SELECT valor FROM config_red WHERE clave = 'texto_explicativo'", fetch=True)
        texto = texto_db['valor'] if texto_db else "🤝 SISTEMA DE SOCIOS Y GANANCIAS\n═══════════════════════\n✅ Al publicar el Bot en tu canal:\n👉 Cuando alguien recargue saldo por tu parte, tú también ganas\n👉 Ejemplo: si tu socio recarga 5 USD → se le agrega a él y tú recibes lo mismo\n📌 ¿Cómo vendes tú?\n1. Usa los métodos de pago que trae el Bot\n2. Cuando te compren (ej: 3 USD Venezuela):\n   • Entra al Bot\n   • Selecciona el país correspondiente\n   • Elige ✍️ cantidad personalizada y pon el monto\n⚠️ IMPORTANTE:\nToda recarga que haga cualquiera que entró por tu enlace, llega al administrador ETIQUETADA CON TU NOMBRE Y TU ID. Al revisar y aprobar el comprobante, el administrador verá claramente «Traído por: TÚ», y te abonará tu ganancia directamente a saldo.\n🔗 TU ENLACE PARA COMPARTIR: `ENLACE`\n═══════════════════════"
        
        link = f"https://t.me/{context.bot.username}?start={user_id}"
        texto_final = texto.replace("`ENLACE`", f"`{link}`")
        
        teclado = [
            [InlineKeyboardButton("📜 HISTORIAL RECARGAS DE MI RED", callback_data="c_red_hist_0")],
            [InlineKeyboardButton("👥 MIS REFERIDOS REGISTRADOS", callback_data="c_red_ref_0")],
            [InlineKeyboardButton("⬅️ VOLVER A MI PERFIL", callback_data="c_perfil_0")]
        ]
        await render_msg(query, context, texto_final, InlineKeyboardMarkup(teclado))

    elif data.startswith("c_red_hist_"):
        pagina = int(data.split("_")[3])
        limite = 5
        recargas = db_query("SELECT * FROM recargas_etiquetadas WHERE vendedor_id = ? ORDER BY id_recarga DESC LIMIT ? OFFSET ?", (user_id, limite, pagina * limite), fetchall=True)
        total_res = db_query("SELECT COUNT(*) as c FROM recargas_etiquetadas WHERE vendedor_id = ?", (user_id,), fetch=True)
        total = total_res['c'] if total_res else 0

        texto = f"📜 **HISTORIAL RECARGAS DE MI RED (Pág {pagina + 1})**\n══════════════════\n"
        for r in recargas:
            texto += f"• **+${r['monto']}** {r['moneda']} | {r['metodo']}\n  👤 ID Cliente: `{r['user_id']}` | 📅 {r['fecha'].split('.')[0]}\n\n"
        if not recargas: texto += "_Aún no tienes recargas registradas en tu red._\n"

        teclado = crear_paginacion(pagina, total, limite, "c_red_hist")
        teclado.append([InlineKeyboardButton("⬅️ VOLVER", callback_data="c_red_inicio")])
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data.startswith("c_red_ref_"):
        pagina = int(data.split("_")[3])
        limite = 8
        referidos = db_query("SELECT r.user_id, r.fecha, u.username FROM red_socios r JOIN usuarios u ON r.user_id = u.user_id WHERE r.invitado_por = ? ORDER BY r.fecha DESC LIMIT ? OFFSET ?", (user_id, limite, pagina * limite), fetchall=True)
        total_res = db_query("SELECT COUNT(*) as c FROM red_socios WHERE invitado_por = ?", (user_id,), fetch=True)
        total = total_res['c'] if total_res else 0

        texto = f"👥 **MIS REFERIDOS REGISTRADOS (Pág {pagina + 1})**\n══════════════════\n"
        for r in referidos:
            n = md_safe(r['username']) if r['username'] else "Sin_Nombre"
            texto += f"👤 {n} (`{r['user_id']}`) | 📅 {r['fecha'].split('.')[0]}\n"
        if not referidos: texto += "_Aún no tienes invitados en tu red._\n"

        teclado = crear_paginacion(pagina, total, limite, "c_red_ref")
        teclado.append([InlineKeyboardButton("⬅️ VOLVER", callback_data="c_red_inicio")])
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

# ==========================================
# PANEL ADMINISTRATIVO Y GESTIÓN
# ==========================================
async def adm_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if esta_ocupado(context):
        await query.answer("⚠️ Espera a terminar la operación actual o usa el botón Cancelar Operación.", show_alert=True)
        return
    await query.answer()
    data = query.data

    if data == "adm_panel":
        teclado = [
            [InlineKeyboardButton("✨ Crear Categoría", callback_data="adm_crear_paquete"), InlineKeyboardButton("📦 Gestión de Inventario", callback_data="adm_inv_pj")],
            [InlineKeyboardButton("💵 Asignar Fondos", callback_data="adm_dar_saldo"), InlineKeyboardButton("🎁 Generar Cupones", callback_data="adm_cupones")],
            [InlineKeyboardButton("📢 Difusión Masiva", callback_data="adm_comunicado"), InlineKeyboardButton("👥 Lista de Usuarios", callback_data="adm_users_0")],
            [InlineKeyboardButton("🔎 Consultar Cliente", callback_data="adm_buscar_usr"), InlineKeyboardButton("🔑 Consultar Key", callback_data="adm_buscar_key_btn")],
            [InlineKeyboardButton("🗑️ Eliminar Usuario", callback_data="adm_borrar_usr"), InlineKeyboardButton("🔄 Reponer Licencia", callback_data="adm_reemplazar")],
            [InlineKeyboardButton("🌎 Divisas y Países", callback_data="adm_paises"), InlineKeyboardButton("🔗 Configuración Web", callback_data="adm_links")],
            [InlineKeyboardButton("💎 RED DE SOCIOS Y GANANCIAS", callback_data="adm_red_panel")],
            [InlineKeyboardButton("🏠 Salir del Panel de Control", callback_data="menu_principal")]
        ]
        await render_msg(query, context, "😈️ **PANEL ADMIN**\nGestión centralizada de tu negocio.", InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_togban_"):
        uid = data.split("_")[2]
        u = db_query("SELECT is_banned FROM usuarios WHERE user_id = ?", (uid,), fetch=True)
        nuevo_estado = 0 if u and u.get('is_banned', 0) else 1
        db_query("UPDATE usuarios SET is_banned = ? WHERE user_id = ?", (nuevo_estado, uid))
        lbl_estado = "Desbaneado 🟢 (Con Acceso)" if nuevo_estado == 0 else "Baneado 🔴 (Sin Acceso)"
        await render_msg(query, context, f"✅ El acceso de la cuenta `{uid}` ahora es: **{lbl_estado}**.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel", callback_data="adm_panel")]]))

    elif data.startswith("adm_rec_apr_"):
        pend_id = data.split("_")[3]
        recarga = db_query("SELECT * FROM recargas_pendientes WHERE id = ?", (pend_id,), fetch=True)

        if not recarga:
            try: await query.message.delete()
            except: pass
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ Esta solicitud de recarga ya fue procesada o ya no existe.")
            return

        uid = recarga['user_id']
        monto = recarga['monto']

        # ACTUALIZAMOS SALDO Y REGISTRAMOS EN EL NUEVO HISTORIAL DE RECARGAS
        db_query("UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?", (monto, uid))
        db_query("INSERT INTO historial_recargas (user_id, monto, moneda, pais) VALUES (?, ?, ?, ?)", (uid, monto, recarga['moneda'], recarga['pais']))
        db_query("DELETE FROM recargas_pendientes WHERE id = ?", (pend_id,))

        try:
            mensaje_exito = f"🎉 **¡FONDOS ACREDITADOS CON ÉXITO!** 🎉\n══════════════════\nHola, te informamos que tu reciente reporte de pago ha sido revisado y **APROBADO** por nuestro equipo financiero.\n\n💰 **Monto depositado en tu cuenta:** ${monto:.2f} USD\n\nTu saldo ya ha sido actualizado y está listo para usarse. ¡Gracias por tu preferencia! 💎"
            await context.bot.send_message(uid, mensaje_exito, parse_mode='Markdown')
        except: pass
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Recarga de **${monto} USD** aprobada exitosamente para el usuario `{uid}`.", parse_mode='Markdown')
        
        # ETIQUETADO AUTOMÁTICO DE SOCIOS (PUNTO A)
        etiqueta_red = registrar_recarga_etiquetada(uid, monto, recarga['moneda'], recarga['pais'], "Comprobante Usuario")
        if etiqueta_red:
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"🏷️ **DETALLE ETIQUETADO DE RED:**{etiqueta_red}", parse_mode='Markdown')
            except: pass
        return

    elif data.startswith("adm_rec_rech_"):
        pend_id = data.split("_")[3]
        recarga = db_query("SELECT user_id FROM recargas_pendientes WHERE id = ?", (pend_id,), fetch=True)

        if recarga:
            uid = recarga['user_id']
            db_query("DELETE FROM recargas_pendientes WHERE id = ?", (pend_id,))
            try:
                mensaje_rechazo = f"❌ **REPORTE DE PAGO RECHAZADO** ❌\n══════════════════\nLamentamos informarte que tu comprobante de pago de saldo no ha podido ser validado por nuestro equipo.\n\n⚠️ _Esto puede deberse a que la imagen no es clara, el monto no coincide, o la transferencia no se reflejó._\n\n👨‍💻 Por favor, contacta a nuestro equipo de Soporte Directo para brindar aclaraciones."
                await context.bot.send_message(uid, mensaje_rechazo, parse_mode='Markdown')
            except: pass
            try: await query.message.delete()
            except: pass
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Recarga denegada y descartada para el usuario `{uid}`.", parse_mode='Markdown')
        else:
            try: await query.message.delete()
            except: pass
            await context.bot.send_message(chat_id=ADMIN_ID, text="❌ Esta solicitud ya había sido procesada.")
        return

    elif data.startswith("adm_socio_apr_"):
        uid = data.split("_")[3]
        precio_sociedad = get_config_float('precio_sociedad', 50.0)

        # AGREGAMOS EL COSTO DE LA SOCIEDAD AL TOTAL GASTADO
        db_query("UPDATE usuarios SET rango = 'socio', total_gastado = total_gastado + ? WHERE user_id = ?", (precio_sociedad, uid))
        try:
            mensaje_exito = f"🎉 **¡MEMBRESÍA SOCIO APROBADA!** 🎉\n══════════════════\nTu reporte de pago ha sido validado. Has sido ascendido oficialmente a **Socio VIP** 💎.\n\nVe al catálogo y explora todos los productos con tus nuevos precios reducidos. ¡Bienvenido al equipo!"
            await context.bot.send_message(uid, mensaje_exito, parse_mode='Markdown')
        except: pass
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"✅ Membresía de Socio VIP otorgada exitosamente al usuario `{uid}`.", parse_mode='Markdown')
        return

    elif data.startswith("adm_socio_rech_"):
        uid = data.split("_")[3]
        try:
            mensaje_rechazo = f"❌ **SOLICITUD VIP RECHAZADA** ❌\n══════════════════\nEl comprobante que enviaste para la Sociedad VIP no fue aprobado. Por favor contacta a Soporte para aclarar la situación."
            await context.bot.send_message(uid, mensaje_rechazo, parse_mode='Markdown')
        except: pass
        try: await query.message.delete()
        except: pass
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"❌ Solicitud de Sociedad VIP denegada al usuario `{uid}`.", parse_mode='Markdown')
        return

    elif data.startswith("adm_rango_"):
        partes = data.split("_")
        uid = partes[2]
        n_rango = partes[3]
        db_query("UPDATE usuarios SET rango = ? WHERE user_id = ?", (n_rango, uid))

        if n_rango == 'socio':
            try: await context.bot.send_message(chat_id=uid, text="💎 **¡FELICIDADES! AHORA ERES SOCIO VIP** 💎\nAcabas de ser promovido por un administrador. A partir de ahora disfrutarás de descuentos exclusivos en todo nuestro catálogo.", parse_mode='Markdown')
            except: pass
        else:
            try: await context.bot.send_message(chat_id=uid, text="👤 **ACTUALIZACIÓN DE RANGO**\nTu cuenta ha sido actualizada al nivel de Cliente Estándar.", parse_mode='Markdown')
            except: pass

        await render_msg(query, context, f"✅ Privilegios del usuario `{uid}` actualizados a nivel **{n_rango.upper()}**.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel", callback_data="adm_panel")]]))

    elif data == "adm_links":
        teclado = [
            [InlineKeyboardButton("✏️ Enlace Soporte", callback_data="adm_edit_soporte"), InlineKeyboardButton("✏️ Enlace Recargas", callback_data="adm_edit_rec")],
            [InlineKeyboardButton("✏️ Canal de Noticias", callback_data="adm_edit_canal"), InlineKeyboardButton("🖼️ Portada (Banner)", callback_data="adm_edit_banner")],
            [InlineKeyboardButton("🖼️ Imagen de Bienvenida", callback_data="adm_edit_img_reg")],
            [InlineKeyboardButton("⚙️ % Beneficio VIP", callback_data="adm_cfg_dsoc"), InlineKeyboardButton("⚙️ % Bono Referidos", callback_data="adm_cfg_cref")],
            [InlineKeyboardButton("⚙️ Precio Sociedad VIP", callback_data="adm_cfg_psoc")],
            [InlineKeyboardButton("⬅️ Volver al Panel de Control", callback_data="adm_panel")]
        ]
        await render_msg(query, context, "⚙️ **CONFIGURACIÓN DEL SISTEMA Y VÍNCULOS**\nConfigura precios, ganancias y enlaces clave.", InlineKeyboardMarkup(teclado))

    elif data == "adm_paises":
        paises = db_query("SELECT * FROM metodos_pais", fetchall=True)
        teclado = [[InlineKeyboardButton(f"{p.get('bandera', '')} {p.get('pais', '')} (1 USD = {p.get('tasa', 1)} {p.get('moneda', '')})", callback_data=f"adm_epais_{p.get('pais', '')}")] for p in paises]
        teclado.append([InlineKeyboardButton("➕ Habilitar Nueva Región/Moneda", callback_data="adm_add_pais"), InlineKeyboardButton("⬅️ Volver al Panel", callback_data="adm_panel")])
        await render_msg(query, context, "🌎 **MÉTODOS DE PAGO Y CONVERSIÓN DE DIVISAS**", InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_epais_"):
        pais = data.split("_", 2)[2]
        teclado = [
            [InlineKeyboardButton("✏️ Ajustar Tasa Cambiaria", callback_data=f"adm_etasa_{pais}")],
            [InlineKeyboardButton("✏️ Modificar Instrucciones", callback_data=f"adm_edet_{pais}")],
            [InlineKeyboardButton("🗑️ Inhabilitar Región", callback_data=f"adm_delpais_{pais}"), InlineKeyboardButton("⬅️ Atrás", callback_data="adm_paises")]
        ]
        await render_msg(query, context, f"⚙️ **EDITANDO PASARELA: {pais}**", InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_delpais_"):
        db_query("DELETE FROM metodos_pais WHERE pais = ?", (data.split("_", 2)[2],))
        await render_msg(query, context, "✅ Región inhabilitada con éxito.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver a Países", callback_data="adm_paises")]]))

    elif data == "adm_cupones":
        teclado = [[InlineKeyboardButton("➕ Emitir Cupón Promocional", callback_data="adm_crear_cupon")], [InlineKeyboardButton("⬅️ Volver al Panel", callback_data="adm_panel")]]
        cupones = db_query("SELECT * FROM cupones", fetchall=True)
        texto = "🎁 **REGISTRO DE CUPONES ACTIVOS**\n\n"
        for c in cupones:
            texto += f"🎟️ Código: `{c.get('codigo')}` | Bono: ${c.get('valor')} | Activaciones: {c.get('usados')}/{c.get('limite')}\n"
        if not cupones: texto += "_No hay cupones vigentes actualmente._"
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_users_"):
        pagina = int(data.split("_")[2])
        limite = 8
        usuarios = db_query("SELECT user_id, username, saldo, rango, is_banned, total_gastado FROM usuarios ORDER BY saldo DESC LIMIT ? OFFSET ?", (limite, pagina * limite), fetchall=True)

        total_res = db_query("SELECT COUNT(*) as c FROM usuarios", fetch=True)
        total = total_res['c'] if total_res else 0

        texto = f"👥 **BASE DE DATOS DE CLIENTES** (Total Registrados: {total})\n_Ordenados por mayor Saldo Disponible_\n\n"
        for u in usuarios:
            status = "🔴 SUSPENDIDO" if u.get('is_banned', 0) else f"🟢 {u.get('rango', 'cliente').upper()}"
            texto += f"🆔 `{u['user_id']}` | {status} | Saldo: **${u.get('saldo', 0.0):.2f}** (Gastó: ${u.get('total_gastado', 0.0):.2f})\n"
        teclado = crear_paginacion(pagina, total, limite, "adm_users")
        teclado.append([InlineKeyboardButton("⬅️ Volver al Panel", callback_data="adm_panel")])
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data == "adm_inv_pj":
        proyectos = db_query("SELECT * FROM proyectos", fetchall=True)
        teclado = [[InlineKeyboardButton(f"📂 {md_safe(p.get('nombre'))}", callback_data=f"adm_inv_pd_{p['id']}")] for p in proyectos]
        teclado.append([InlineKeyboardButton("⬅️ Volver al Panel", callback_data="adm_panel")])
        await render_msg(query, context, "📦 **ESTRUCTURA DE CATÁLOGO (Selecciona Categoría):**", InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_inv_pd_"):
        pid = data.split("_")[3]
        pj = db_query("SELECT * FROM proyectos WHERE id = ?", (pid,), fetch=True)
        productos = db_query("SELECT * FROM productos WHERE proyecto_id = ?", (pid,), fetchall=True)
        teclado = [[InlineKeyboardButton(f"📦 {md_safe(p.get('nombre'))}", callback_data=f"adm_inv_dur_{p['id']}")] for p in productos]
        teclado.append([InlineKeyboardButton("🖼️ Subir Portada de la Categoría", callback_data=f"adm_img_pj_{pid}")])
        teclado.append([InlineKeyboardButton("➕ Añadir Nuevo Artículo", callback_data=f"adm_addprod_{pid}")])
        teclado.append([InlineKeyboardButton("🗑️ Destruir Categoría Completa", callback_data=f"adm_del_pj_{pid}"), InlineKeyboardButton("⬅️ Atrás", callback_data="adm_inv_pj")])
        await render_msg(query, context, f"📦 **ADMINISTRANDO CATEGORÍA: {md_safe(pj.get('nombre'))}**", InlineKeyboardMarkup(teclado), pj.get('imagen'))

    elif data.startswith("adm_inv_dur_"):
        pdid = data.split("_")[3]
        p_info = db_query("SELECT proyecto_id, nombre, link_descarga, link_tutorial, imagen FROM productos WHERE id = ?", (pdid,), fetch=True)
        duraciones = db_query("SELECT * FROM duraciones WHERE producto_id = ?", (pdid,), fetchall=True)
        texto_links = f"🔗 Link de Descarga Anexado: {'✅ Sí' if p_info.get('link_descarga') else '❌ No'}\n📺 Manual de Instalación Anexado: {'✅ Sí' if p_info.get('link_tutorial') else '❌ No'}"
        teclado = [[InlineKeyboardButton("🔗 Asignar URL Descarga", callback_data=f"adm_linkdesc_{pdid}"), InlineKeyboardButton("📺 Asignar URL Manual", callback_data=f"adm_linktut_{pdid}")]]

        for d in duraciones:
            stock_res = db_query("SELECT COUNT(*) as c FROM keys WHERE duracion_id = ? AND vendida = 0", (d['id'],), fetch=True)
            stock = stock_res['c'] if stock_res else 0

            str_precio = f"${d.get('precio', 0.0)}" + (f" (VIP: ${d.get('precio_socio')})" if d.get('precio_socio', 0.0) > 0 else "")
            teclado.append([InlineKeyboardButton(f"⏳ {d.get('dias')}d | {str_precio} | Stock disponible: {stock}", callback_data=f"adm_edit_dur_{d['id']}")])

        teclado.append([InlineKeyboardButton("🖼️ Subir Portada del Artículo", callback_data=f"adm_img_pd_{pdid}")])
        teclado.append([InlineKeyboardButton("➕ Añadir Nueva Opción de Duración", callback_data=f"adm_adddur_{pdid}")])
        teclado.append([InlineKeyboardButton("✏️ Modificar Nombre del Artículo", callback_data=f"adm_renprod_{pdid}")])
        teclado.append([InlineKeyboardButton("🗑️ Retirar Artículo del Catálogo", callback_data=f"adm_del_pd_{pdid}"), InlineKeyboardButton("⬅️ Atrás", callback_data=f"adm_inv_pd_{p_info.get('proyecto_id')}")])
        await render_msg(query, context, f"⏱️ **ADMINISTRANDO ARTÍCULO: {md_safe(p_info.get('nombre'))}**\n{texto_links}", InlineKeyboardMarkup(teclado), p_info.get('imagen'))

    elif data.startswith("adm_edit_dur_"):
        dur_id = data.split("_")[3]
        d = db_query("SELECT * FROM duraciones WHERE id = ?", (dur_id,), fetch=True)
        texto = f"⚙️ **AJUSTANDO PERIODO** ({d.get('dias')} días)\n💵 Precio Normal: ${d.get('precio')} | Precio VIP: ${d.get('precio_socio')}\n🔥 Oferta Flash Activa: {'Sí (Rebajado a $'+str(d.get('precio_oferta'))+')' if d.get('en_oferta') else 'No'}"
        teclado = [
            [InlineKeyboardButton("➕ Subir Inventario (Añadir Keys)", callback_data=f"adm_add_key_{dur_id}"), InlineKeyboardButton("✏️ Actualizar Tarifas", callback_data=f"adm_edit_pr_{dur_id}")],
            [InlineKeyboardButton("⚡ Configurar Oferta Flash", callback_data=f"adm_oferta_{dur_id}"), InlineKeyboardButton("🗑️ Borrar esta Duración", callback_data=f"adm_del_dur_{dur_id}")],
            [InlineKeyboardButton("⬅️ Regresar al Artículo", callback_data=f"adm_inv_dur_{d.get('producto_id')}")]
        ]
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_busc_res_"):
        uid = data.split("_")[3]
        u = db_query("SELECT * FROM usuarios WHERE user_id = ?", (uid,), fetch=True)
        if not u:
            await query.answer("Usuario no encontrado.", show_alert=True)
            return

        res_keys = db_query("SELECT COUNT(*) as c FROM keys WHERE comprador_id = ?", (uid,), fetch=True)
        keys = res_keys['c'] if res_keys else 0

        status_ban = "🔴 CUENTA SUSPENDIDA" if u.get('is_banned', 0) else "🟢 Operativo y Activo"
        btn_ban_lbl = "🔓 Reactivar Acceso a Cuenta" if u.get('is_banned', 0) else "🔨 Suspender Acceso a Cuenta"

        u_name = md_safe(u.get('username') if u.get('username') else "Sin_Nombre")
        u_tel = md_safe(u.get('telefono') if u.get('telefono') else "No_Proporcionado")
        u_rango = md_safe(u.get('rango', 'cliente')).upper()

        txt = f"🔎 **REPORTE MEGA DETALLADO DE CLIENTE**\n══════════════════\n🆔 ID Universal: `{uid}`\n👤 Tag de Usuario: {u_name}\n📱 Número Móvil: {u_tel}\n🌟 Nivel de Privilegios: **{u_rango}**\n💰 Capital Actual: **${u.get('saldo', 0.0):.2f} USD**\n🔥 **TOTAL INVERTIDO EN TIENDA:** **${u.get('total_gastado', 0.0):.2f} USD**\n🔑 Licencias Adquiridas: {keys} Unidades\n⚠️ Estado General: **{status_ban}**\n══════════════════"

        btns = [
            [InlineKeyboardButton("📜 Historial de Recargas", callback_data=f"adm_uhist_rec_{uid}_0")],
            [InlineKeyboardButton("🔑 Historial de Claves y Productos", callback_data=f"adm_uhist_key_{uid}_0")],
            [InlineKeyboardButton("Ascender a Nivel Socio VIP", callback_data=f"adm_rango_{uid}_socio"), InlineKeyboardButton("Degradar a Cliente", callback_data=f"adm_rango_{uid}_cliente")],
            [InlineKeyboardButton(btn_ban_lbl, callback_data=f"adm_togban_{uid}")],
            [InlineKeyboardButton("🏠 Regresar al Panel de Control", callback_data="adm_panel")]
        ]
        await render_msg(query, context, txt, InlineKeyboardMarkup(btns))

    elif data.startswith("adm_uhist_rec_"):
        partes = data.split("_")
        uid = partes[3]
        pagina = int(partes[4])
        limite = 5

        total_res = db_query("SELECT COUNT(*) as c FROM historial_recargas WHERE user_id = ?", (uid,), fetch=True)
        total = total_res['c'] if total_res else 0
        total_paginas = (total + limite - 1) // limite if total > 0 else 1

        recargas = db_query("SELECT monto, moneda, pais, datetime(fecha, 'localtime') as fecha_f FROM historial_recargas WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (uid, limite, pagina * limite), fetchall=True)

        txt = f"📜 **HISTORIAL DE RECARGAS**\n👤 Usuario: `{uid}`\n📄 **Página {pagina + 1} / {total_paginas}**\n══════════════════\n"
        if recargas:
            for r in recargas:
                txt += f"• **+${r['monto']}** {r['moneda']} | {r['pais']} | 📅 {r['fecha_f']}\n"
        else:
            txt += "_El usuario no cuenta con historial de recargas registrado._\n"

        teclado = crear_paginacion(pagina, total, limite, f"adm_uhist_rec_{uid}")
        teclado.append([InlineKeyboardButton("⬅️ Volver al Perfil del Usuario", callback_data=f"adm_busc_res_{uid}")])

        await render_msg(query, context, txt, InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_uhist_key_"):
        partes = data.split("_")
        uid = partes[3]
        pagina = int(partes[4])
        limite = 5

        total_res = db_query("SELECT COUNT(*) as c FROM keys WHERE comprador_id = ? AND fecha_compra IS NOT NULL", (uid,), fetch=True)
        total = total_res['c'] if total_res else 0
        total_paginas = (total + limite - 1) // limite if total > 0 else 1

        compras = db_query("SELECT k.llave, p.nombre, d.dias, datetime(k.fecha_compra, 'localtime') as fecha_f FROM keys k JOIN duraciones d ON k.duracion_id=d.id JOIN productos p ON d.producto_id=p.id WHERE k.comprador_id = ? AND k.fecha_compra IS NOT NULL ORDER BY k.fecha_compra DESC LIMIT ? OFFSET ?", (uid, limite, pagina * limite), fetchall=True)

        txt = f"🔑 **HISTORIAL DE PRODUCTOS Y CLAVES**\n👤 Usuario: `{uid}`\n📄 **Página {pagina + 1} / {total_paginas}**\n══════════════════\n"
        if compras:
            for c in compras:
                txt += f"• **{md_safe(c['nombre'])}** ({c['dias']}d) ➔ Entregado: {c['fecha_f']}\n  🔑 Clave: `{c['llave']}`\n\n"
        else:
            txt += "_El usuario no cuenta con compras recientes registradas._\n"

        teclado = crear_paginacion(pagina, total, limite, f"adm_uhist_key_{uid}")
        teclado.append([InlineKeyboardButton("⬅️ Volver al Perfil del Usuario", callback_data=f"adm_busc_res_{uid}")])

        await render_msg(query, context, txt, InlineKeyboardMarkup(teclado))

    elif data.startswith("adm_del_"):
        acc, pid = data.split("_")[2], data.split("_")[3]
        if acc == "pj":
            prods = db_query("SELECT id FROM productos WHERE proyecto_id = ?", (pid,), fetchall=True)
            for p in prods:
                db_query("DELETE FROM duraciones WHERE producto_id = ?", (p['id'],))
            db_query("DELETE FROM productos WHERE proyecto_id = ?", (pid,))
            db_query("DELETE FROM proyectos WHERE id = ?", (pid,))
        elif acc == "pd":
            db_query("DELETE FROM duraciones WHERE producto_id = ?", (pid,))
            db_query("DELETE FROM productos WHERE id = ?", (pid,))
        elif acc == "dur":
            db_query("DELETE FROM duraciones WHERE id = ?", (pid,))

        await render_msg(query, context, "✅ Registro eliminado exitosamente de la base de datos de la tienda.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver al Inventario Central", callback_data="adm_inv_pj")]]))

    elif data == "adm_red_panel":
        cfg = db_query("SELECT valor FROM config_red WHERE clave = 'sistema_activo'", fetch=True)
        estado = "🟢 ACTIVADO" if (cfg and cfg['valor'] == '1') else "🔴 DESACTIVADO"
        
        teclado = [
            [InlineKeyboardButton(f"Cambiar Estado: {estado}", callback_data="adm_red_toggle")],
            [InlineKeyboardButton("📜 Historial Global Completo", callback_data="adm_red_global_0")],
            [InlineKeyboardButton("⬅️ Regresar al Panel", callback_data="adm_panel")]
        ]
        await render_msg(query, context, f"💎 **PANEL RED DE SOCIOS**\nGestión de afiliados y recargas etiquetadas.\nEstado actual del sistema: **{estado}**", InlineKeyboardMarkup(teclado))

    elif data == "adm_red_toggle":
        cfg = db_query("SELECT valor FROM config_red WHERE clave = 'sistema_activo'", fetch=True)
        nuevo_val = '0' if (cfg and cfg['valor'] == '1') else '1'
        db_query("UPDATE config_red SET valor = ? WHERE clave = 'sistema_activo'", (nuevo_val,))
        await render_msg(query, context, "✅ Estado del sistema de socios actualizado.", InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="adm_red_panel")]]))

    elif data.startswith("adm_red_global_"):
        pagina = int(data.split("_")[3])
        limite = 5
        recargas = db_query("SELECT * FROM recargas_etiquetadas ORDER BY id_recarga DESC LIMIT ? OFFSET ?", (limite, pagina * limite), fetchall=True)
        total_res = db_query("SELECT COUNT(*) as c FROM recargas_etiquetadas", fetch=True)
        total = total_res['c'] if total_res else 0

        texto = f"📜 **HISTORIAL GLOBAL ETIQUETADO (Pág {pagina + 1})**\n══════════════════\n"
        for r in recargas:
            texto += f"• **+${r['monto']}** {r['moneda']} | {r['metodo']}\n  Vendedor: {md_safe(r['vendedor_nombre'])} (`{r['vendedor_id']}`)\n  Cliente: `{r['user_id']}` | 📅 {r['fecha'].split('.')[0]}\n\n"
        if not recargas: texto += "_Aún no hay recargas etiquetadas registradas._\n"
        
        teclado = crear_paginacion(pagina, total, limite, "adm_red_global")
        teclado.append([InlineKeyboardButton("⬅️ Volver al Submenú", callback_data="adm_red_panel")])
        await render_msg(query, context, texto, InlineKeyboardMarkup(teclado))

# ==========================================
# RUTINAS Y FORMULARIOS DE TEXTO
# ==========================================
async def conv_start_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if usuario_baneado(query.from_user.id):
        await query.answer("Acceso Denegado.", show_alert=True)
        return

    await query.answer()
    marcar_ocupado(context, True)
    cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]])

    if query.data == "c_cupon":
        msg = await render_msg(query, context, "🎟️ **CENTRO DE PROMOCIONES**\nIngresa cuidadosamente el código exacto de tu cupón de regalo:", cancel)
        context.user_data['prompt_msg_id'] = msg.message_id
        return CANJEAR_CUPON

    elif query.data.startswith("c_reccustom_"):
        pais = query.data.split("_")[2]
        context.user_data['recarga_pais'] = pais
        msg = await render_msg(query, context, f"💵 **{pais} - MONTO PERSONALIZADO**\n\nPor favor, ingresa el monto en USD que deseas recargar (Mínimo $3.00 USD):", cancel)
        context.user_data['prompt_msg_id'] = msg.message_id
        return CUSTOM_RECARGA

    elif query.data.startswith("c_recm_"):
        partes = query.data.split("_")
        monto = float(partes[-1])
        pais = "_".join(partes[2:-1])

        context.user_data['recarga_monto'] = monto
        context.user_data['recarga_pais'] = pais

        p_info = db_query("SELECT * FROM metodos_pais WHERE pais = ?", (pais,), fetch=True)
        monto_local = monto * p_info.get('tasa', 1)
        texto = f"💳 **FICHA DE DEPÓSITO DE SALDO ({p_info.get('bandera', '')} {pais})**\n\nDebes transferir la cantidad exacta de: **${monto_local:,.2f} {p_info.get('moneda', '')}**\n(Para obtener ${monto} USD en el bot)\n\n📌 **Bancos / Instrucciones de pago:**\n{p_info.get('detalles', '')}\n\n📸 **Adjunta y envía la fotografía (imagen) de tu comprobante de pago bancario en este chat para revisión:**"
        msg = await render_msg(query, context, texto, cancel)
        context.user_data['prompt_msg_id'] = msg.message_id
        return ENVIAR_COMPROBANTE

    elif query.data.startswith("c_qtycustom_"):
        _, _, dur_id, precio = query.data.split("_")
        context.user_data['buy_dur_id'] = dur_id
        context.user_data['buy_precio'] = precio
        msg = await render_msg(query, context, "🛒 **CANTIDAD LIBRE**\n\nPor favor, escribe con números la cantidad exacta de licencias que deseas adquirir (Ejemplo: 3):", cancel)
        context.user_data['prompt_msg_id'] = msg.message_id
        return CUSTOM_QTY

    elif query.data.startswith("c_socp_"):
        pais = "_".join(query.data.split("_")[2:])
        context.user_data['socio_pais'] = pais
        precio_sociedad = get_config_float('precio_sociedad', 50.0)

        p_info = db_query("SELECT * FROM metodos_pais WHERE pais = ?", (pais,), fetch=True)
        monto_local = precio_sociedad * p_info.get('tasa', 1)
        texto = f"🟢 **FICHA DE PAGO PARA SOCIEDAD VIP ({p_info.get('bandera', '')} {pais})**\n\nPara adquirir tu membresía, debes transferir: **${monto_local:,.2f} {p_info.get('moneda', '')}**\n(Equivalente a ${precio_sociedad} USD)\n\n📌 **Cuentas Bancarias / Instrucciones:**\n{p_info.get('detalles', '')}\n\n📸 **Por favor, envía la FOTO de tu comprobante de depósito aquí en el chat para proceder a otorgarte el rango:**"
        msg = await render_msg(query, context, texto, cancel)
        context.user_data['prompt_msg_id'] = msg.message_id
        return ENVIAR_COMP_SOCIEDAD

async def conv_start_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    marcar_ocupado(context, True)
    cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]])
    msg = None
    ret = ConversationHandler.END

    if data == "adm_crear_paquete":
        msg = await render_msg(query, context, "1️⃣ Ingresa el Título o Nombre de la **NUEVA CATEGORÍA**:", cancel)
        ret = CREAR_PAQUETE_PROJ
    elif data.startswith("adm_addprod_"):
        context.user_data['tmp_proj_id'] = data.split("_")[2]
        msg = await render_msg(query, context, "📦 Ingresa el Título del **NUEVO ARTÍCULO**:", cancel)
        ret = ADD_PROD_NAME
    elif data.startswith("adm_adddur_"):
        context.user_data['tmp_prod_id'] = data.split("_")[2]
        msg = await render_msg(query, context, "⏱️ Configuración de **DURACIÓN Y COSTOS**\nRespeta el formato exacto: `Dias,PrecioBase,PrecioVIP`\n(Ejemplo: `30,15.50,10.00`):", cancel)
        ret = ADD_DUR_DUR
    elif data.startswith("adm_renprod_"):
        context.user_data['tmp_prod_id'] = data.split("_")[2]
        msg = await render_msg(query, context, "✏️ Redacta el **NUEVO TÍTULO** del artículo para actualizarlo:", cancel)
        ret = RENOMBRAR_PROD
    elif data == "adm_dar_saldo":
        msg = await render_msg(query, context, "💵 **GESTOR MANUAL DE FONDOS**\nFormato exacto: `ID Monto` (Ej: `1234567 50.00`)\n_(Usa el símbolo negativo `-` si necesitas deducir saldo)_", cancel)
        ret = DAR_SALDO
    elif data == "adm_comunicado":
        msg = await render_msg(query, context, "📢 **COMUNICADO OFICIAL DEL SISTEMA**\nEscribe el texto del mensaje que se enviará masivamente a todos los clientes:", cancel)
        ret = COM_TEXT
    elif data == "adm_crear_cupon":
        msg = await render_msg(query, context, "🎟️ Escribe la **CLAVE DEL CUPÓN** (Por ejemplo: VERANO2024):", cancel)
        ret = CREAR_CUPON_COD
    elif data == "adm_borrar_usr":
        msg = await render_msg(query, context, "🗑️ **ELIMINAR USUARIO DEL SISTEMA**\nProporciona el ID numérico del cliente a eliminar de la base de datos de manera irreversible:", cancel)
        ret = BORRAR_USER
    elif data == "adm_buscar_usr":
        msg = await render_msg(query, context, "🔎 **INSPECTOR DE CUENTAS**\nIngresa el Username o ID Numérico del usuario que deseas investigar minuciosamente:", cancel)
        ret = BUSCAR_USER
    elif data == "adm_buscar_key_btn":
        msg = await render_msg(query, context, "🔎 **INSPECTOR DE CLAVES (KEYS)**\nIngresa o pega la Key que deseas consultar para ver su vigencia y detalles exactos:", cancel)
        ret = BUSCAR_KEY_ADM
    elif data == "adm_reemplazar":
        msg = await render_msg(query, context, "🔄 **SISTEMA DE GARANTÍAS**\nPega la Credencial (Key) defectuosa que reportó el cliente y que deseas sustituir por una nueva:", cancel)
        ret = REEMPLAZAR_KEY
    elif data == "adm_add_pais":
        msg = await render_msg(query, context, "🌎 **HABILITAR NUEVA REGIÓN / MÉTODO**\nFormato: `País,Bandera,Moneda`\n(Ejemplo exacto: `Perú,🇵🇪,PEN`)", cancel)
        ret = ADD_PAIS_NOM
    elif data.startswith("adm_etasa_"):
        context.user_data['tmp_pais'] = data.split("_", 2)[2]
        msg = await render_msg(query, context, "💱 Ingresa la **NUEVA TASA DE CONVERSIÓN** frente al Dólar (Ej: Escribe `17.50` para que 1 USD se calcule como 17.50 de su moneda):", cancel)
        ret = EDIT_PAIS_TASA
    elif data.startswith("adm_edet_"):
        context.user_data['tmp_pais'] = data.split("_", 2)[2]
        msg = await render_msg(query, context, "✏️ Redacta la guía e instrucciones completas de depósito para los clientes de esta región (Cuentas, titulares, conceptos):", cancel)
        ret = EDIT_PAIS_DET
    elif data.startswith("adm_edit_pr_"):
        context.user_data['tmp_dur_id'] = data.split("_")[3]
        msg = await render_msg(query, context, "✏️ **REESTRUCTURACIÓN DE TARIFAS**\nFormato: `PrecioCliente,PrecioSocioVIP` (Ejemplo: `15.50,12.00`):", cancel)
        ret = EDIT_PRECIO
    elif data.startswith("adm_oferta_"):
        context.user_data['tmp_dur_id'] = data.split("_")[2]
        msg = await render_msg(query, context, "⚡ **CONFIGURAR OFERTA FLASH**\nIngresa la tarifa rebajada (Manda el número `0` para apagar la promoción):", cancel)
        ret = OFERTA_PRECIO
    elif data.startswith("adm_add_key_"):
        context.user_data['tmp_dur_id'] = data.split("_")[3]
        msg = await render_msg(query, context, "🔑 **INYECTAR INVENTARIO (LICENCIAS)**\nPega tus licencias listas para vender (Sepáralas de modo que quede Una en cada línea de texto):", cancel)
        ret = ADD_KEYS
    elif data.startswith("adm_linkdesc_"):
        context.user_data['tmp_prod_id'] = data.split("_")[2]
        msg = await render_msg(query, context, "📥 Pega la URL directa o del servidor de Descarga para este producto:", cancel)
        ret = ADD_LINK_DESC
    elif data.startswith("adm_linktut_"):
        context.user_data['tmp_prod_id'] = data.split("_")[2]
        msg = await render_msg(query, context, "📺 Pega la URL del Video de Youtube o Guía de Instalación:", cancel)
        ret = ADD_LINK_TUT
    elif data == "adm_edit_soporte":
        msg = await render_msg(query, context, "🔗 Pega la URL o Link del Chat de Soporte Técnico (Ej: https://t.me/UsuarioSoporte):", cancel)
        ret = EDIT_SOPORTE
    elif data == "adm_edit_rec":
        msg = await render_msg(query, context, "📲 Pega la URL del Asesor de Recargas o Cajero (Para los pagos manuales asistidos):", cancel)
        ret = EDIT_METODOS
    elif data == "adm_edit_canal":
        msg = await render_msg(query, context, "🔗 Pega la URL de tu Canal de Noticias u Ofertas Oficial:", cancel)
        ret = EDIT_CANAL
    elif data == "adm_cfg_dsoc":
        msg = await render_msg(query, context, "⚙️ Digita el porcentaje de rebaja automática para el nivel de Socio VIP (Ej: Escribir `20` implica un 20% más barato):", cancel)
        ret = CFG_DESC_SOCIO
    elif data == "adm_cfg_cref":
        msg = await render_msg(query, context, "⚙️ Digita el porcentaje de comisión que ganan los Invitadores (Ej: Escribir `5` implica ganar el 5% de lo que gasten sus referidos):", cancel)
        ret = CFG_COM_REF
    elif data == "adm_cfg_psoc":
        msg = await render_msg(query, context, "⚙️ Digita el COSTO en USD que los usuarios deberán pagar para adquirir la Sociedad VIP (Membresía):", cancel)
        ret = EDIT_PRECIO_SOCIEDAD
    elif data == "adm_edit_banner":
        msg = await render_msg(query, context, "🖼️ Envía la FOTOGRAFÍA o pega la URL de la portada principal del menú (Manda `0` para desactivarla):", cancel)
        ret = EDIT_BANNER
    elif data == "adm_edit_img_reg":
        msg = await render_msg(query, context, "🖼️ Envía la FOTOGRAFÍA de Bienvenida que aparece al usar el comando /start por primera vez (Manda `0` para ocultarla):", cancel)
        ret = EDIT_IMG_REG
    elif data.startswith("adm_img_pj_"):
        context.user_data['tmp_pj_id'] = data.split("_")[3]
        msg = await render_msg(query, context, "🖼️ Envía o Carga la FOTO miniatura para esta CATEGORÍA (Manda `0` para no usar foto):", cancel)
        ret = EDIT_IMG_PJ
    elif data.startswith("adm_img_pd_"):
        context.user_data['tmp_pd_id'] = data.split("_")[3]
        msg = await render_msg(query, context, "🖼️ Envía o Carga la FOTO miniatura para este ARTÍCULO (Manda `0` para no usar foto):", cancel)
        ret = EDIT_IMG_PD

    if msg:
        context.user_data['prompt_msg_id'] = msg.message_id
    return ret

async def cl_custom_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        monto = float(update.message.text.strip())
        if monto < 3.0:
            await update_form(update, context, "❌ El monto mínimo de recarga es de **$3.00 USD**. Por favor, ingresa un monto válido:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cb")]]))
            return CUSTOM_RECARGA

        context.user_data['recarga_monto'] = monto
        pais = context.user_data.get('recarga_pais')

        p_info = db_query("SELECT * FROM metodos_pais WHERE pais = ?", (pais,), fetch=True)
        monto_local = monto * p_info.get('tasa', 1)
        texto = f"💳 **FICHA DE DEPÓSITO DE SALDO ({p_info.get('bandera', '')} {pais})**\n\nDebes transferir la cantidad exacta de: **${monto_local:,.2f} {p_info.get('moneda', '')}**\n(Para obtener ${monto} USD en el bot)\n\n📌 **Bancos / Instrucciones de pago:**\n{p_info.get('detalles', '')}\n\n📸 **Adjunta y envía la fotografía (imagen) de tu comprobante de pago bancario en este chat para revisión:**"
        cancel = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]])
        await update_form(update, context, texto, cancel)
        return ENVIAR_COMPROBANTE
    except ValueError:
        await update_form(update, context, "❌ Monto inválido. Ingresa únicamente el número del saldo que deseas en USD (ej: `5.50`):", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cb")]]))
        return CUSTOM_RECARGA

async def cl_custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        if qty <= 0: raise ValueError

        dur_id = context.user_data['buy_dur_id']
        precio = float(context.user_data['buy_precio'])

        stock_res = db_query("SELECT COUNT(*) as c FROM keys WHERE duracion_id = ? AND vendida = 0", (dur_id,), fetch=True)
        stock = stock_res['c'] if stock_res else 0

        if qty > stock:
            await update_form(update, context, f"❌ Stock insuficiente. Solo hay **{stock}** licencias disponibles. Por favor, ingresa una cantidad menor o igual:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cb")]]))
            return CUSTOM_QTY

        total_pagar = precio * qty
        user_id = update.effective_user.id
        user_db = db_query("SELECT saldo FROM usuarios WHERE user_id = ?", (user_id,), fetch=True)

        d_info = db_query("SELECT d.dias, p.nombre, p.imagen FROM duraciones d JOIN productos p ON d.producto_id=p.id WHERE d.id = ?", (dur_id,), fetch=True)

        if user_db.get('saldo', 0.0) < total_pagar:
            teclado = [[InlineKeyboardButton("💳 Ir a Recargar Saldo", callback_data="c_recargar")], [InlineKeyboardButton("❌ Cancelar", callback_data="menu_principal")]]
            await update_form(update, context, f"❌ **SALDO INSUFICIENTE**\n\nCosto total de la Orden: **${total_pagar:.2f} USD**\nTu saldo actual es de: **${user_db.get('saldo', 0.0):.2f} USD**", InlineKeyboardMarkup(teclado))
            marcar_ocupado(context, False)
            return ConversationHandler.END

        restante = user_db.get('saldo', 0.0) - total_pagar
        resumen = f"⚠️ **RESUMEN DE TU COMPRA**\n══════════════════\n📦 Producto a entregar: **{md_safe(d_info.get('nombre'))}**\n⏱️ Vigencia de Licencia: **{d_info.get('dias')} Días**\n🔑 Unidades seleccionadas: **{qty} Licencia(s)**\n\n💰 Tu Saldo actual: **${user_db.get('saldo', 0.0):.2f} USD**\n📉 Tu Saldo tras la compra: **${restante:.2f} USD**\n\n¿Deseas confirmar y procesar esta transacción?"
        teclado = [[InlineKeyboardButton("✅ SÍ, CONFIRMAR Y PAGAR", callback_data=f"c_buy_{dur_id}_{precio}_{qty}")], [InlineKeyboardButton("❌ Cancelar Orden", callback_data="menu_principal")]]
        await update_form(update, context, resumen, InlineKeyboardMarkup(teclado))
        marcar_ocupado(context, False)
        return ConversationHandler.END
    except ValueError:
        await update_form(update, context, "❌ Cantidad inválida. Ingresa un número entero mayor a cero (ejemplo: `3`):", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_cb")]]))
        return CUSTOM_QTY

async def cl_cupon_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        codigo = update.message.text.strip().upper()
        user_id = update.effective_user.id
        cup = db_query("SELECT * FROM cupones WHERE codigo = ?", (codigo,), fetch=True)
        teclado = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Menú de Inicio", callback_data="menu_principal")]])

        if not cup:
            await update_form(update, context, "❌ El código promocional ingresado es incorrecto o no existe en el sistema.", teclado)
            return ConversationHandler.END
        if cup.get('usados', 0) >= cup.get('limite', 1):
            await update_form(update, context, "❌ Lo sentimos, este cupón promocional ya ha alcanzado su límite máximo de usos disponibles.", teclado)
            return ConversationHandler.END
        if db_query("SELECT * FROM cupones_usados WHERE codigo = ? AND user_id = ?", (codigo, user_id), fetch=True):
            await update_form(update, context, "❌ Ya has reclamado esta promoción en tu cuenta con anterioridad. Los cupones son de un solo uso por persona.", teclado)
            return ConversationHandler.END

        db_query("UPDATE cupones SET usados = usados + 1 WHERE codigo = ?", (codigo,))
        db_query("INSERT INTO cupones_usados (codigo, user_id) VALUES (?, ?)", (codigo, user_id))
        db_query("UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?", (cup.get('valor', 0), user_id))
        await update_form(update, context, f"🎉 **¡CUPÓN APLICADO CON ÉXITO!**\n\nEl sistema acaba de depositar un bono de regalo equivalente a **${cup.get('valor', 0):.2f} USD** directamente en tu balance. ¡Disfrútalo!", teclado)
    except Exception as e:
        logger.error(f"Error procesando cupón: {e}")
        await update_form(update, context, "❌ Error de procesamiento. Revisa el código.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu_principal")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def cl_comprobante_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message.photo:
            await update_form(update, context, "⚠️ Archivo no válido. El sistema de validación requiere que envíes forzosamente una **FOTO o CAPTURA DE PANTALLA** del comprobante bancario. Inténtalo de nuevo.", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abortar Transacción", callback_data="cancelar_cb")]]))
            return ENVIAR_COMPROBANTE

        foto = update.message.photo[-1].file_id
        user_id = update.effective_user.id
        monto = context.user_data.get('recarga_monto', 0)
        pais = context.user_data.get('recarga_pais', 'No Especificado')

        # OBTENEMOS LA MONEDA PARA EL HISTORIAL
        p_info = db_query("SELECT moneda FROM metodos_pais WHERE pais = ?", (pais,), fetch=True)
        moneda = p_info['moneda'] if p_info else 'USD'

        # GUARDAMOS LA RECARGA COMO PENDIENTE PARA EVITAR LIMITES DE TELEGRAM
        pend_id = 0
        with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO recargas_pendientes (user_id, monto, pais, moneda) VALUES (?, ?, ?, ?)", (user_id, monto, pais, moneda))
            pend_id = c.lastrowid
            conn.commit()

        u_name = update.effective_user.username
        display_name = md_safe(f"@{u_name}" if u_name else "Sin_Username")

        mensaje_cliente = (
            "✅ **¡COMPROBANTE RECIBIDO Y REGISTRADO!** ✅\n\n"
            "Tu reporte de pago de saldo ha sido enviado al equipo financiero para su validación manual.\n\n"
            "⏳ _El tiempo estimado de revisión suele ser de unos minutos. Serás notificado automáticamente por este medio en cuanto tu dinero sea acreditado. Gracias por tu paciencia._"
        )

        await update_form(update, context, mensaje_cliente, InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ir al Catálogo de la Tienda", callback_data="menu_principal")]]))

        teclado_admin = [
            [InlineKeyboardButton(f"✅ Autorizar Recarga de ${monto}", callback_data=f"adm_rec_apr_{pend_id}"), InlineKeyboardButton("❌ Denegar Recarga", callback_data=f"adm_rec_rech_{pend_id}")],
            [InlineKeyboardButton("💬 Abrir Chat Privado con Cliente", url=f"tg://user?id={user_id}")]
        ]

        caption_admin = (
            f"💳 **[RECARGA SALDO] NUEVO REPORTE DE DEPÓSITO**\n"
            f"══════════════════\n"
            f"🌎 **País / Método usado:** {pais}\n"
            f"💰 **Monto Solicitado a Cargar:** ${monto} USD\n"
            f"👤 **Usuario Solicitante:** {display_name}\n"
            f"🆔 **ID de Cuenta:** `{user_id}`\n"
            f"══════════════════\n"
            f"Verifica que el comprobante adjunto coincida con la cantidad solicitada y toma una decisión."
        )

        await context.bot.send_photo(chat_id=ADMIN_ID, photo=foto, caption=caption_admin, reply_markup=InlineKeyboardMarkup(teclado_admin), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error procesando comprobante de saldo: {e}")
        await update_form(update, context, "❌ Ocurrió un error guardando tu imagen. Por favor reintenta.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu_principal")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def cl_comprobante_soc_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message.photo:
            await update_form(update, context, "⚠️ Documento inválido. Debes enviar una **IMAGEN/CAPTURA** del comprobante para procesar tu Sociedad VIP.", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Abortar Compra VIP", callback_data="cancelar_cb")]]))
            return ENVIAR_COMP_SOCIEDAD

        foto = update.message.photo[-1].file_id
        user_id = update.effective_user.id
        pais = context.user_data.get('socio_pais', 'No Especificado')
        precio_sociedad = get_config_float('precio_sociedad', 50.0)

        u_name = update.effective_user.username
        display_name = md_safe(f"@{u_name}" if u_name else "Sin_Username")

        mensaje_cliente = (
            "✅ **¡SOLICITUD DE SOCIEDAD RECIBIDA CON ÉXITO!** ✅\n\n"
            "Hemos capturado tu comprobante. Los administradores lo están revisando para validarlo.\n\n"
            "⏳ _Serás notificado en breve. Una vez aceptado, tu rango cambiará de manera instantánea y podrás disfrutar de todos tus beneficios._"
        )

        await update_form(update, context, mensaje_cliente, InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Ir al Menú de Inicio", callback_data="menu_principal")]]))

        teclado_admin = [
            [InlineKeyboardButton(f"✅ Aprobar como Socio VIP", callback_data=f"adm_socio_apr_{user_id}"), InlineKeyboardButton("❌ Denegar Solicitud", callback_data=f"adm_socio_rech_{user_id}")],
            [InlineKeyboardButton("💬 Hablar con el Cliente", url=f"tg://user?id={user_id}")]
        ]

        caption_admin = (
            f"💎 **[NUEVO SOCIO VIP] SOLICITUD DE ASCENSO**\n"
            f"══════════════════\n"
            f"🌎 **País / Método:** {pais}\n"
            f"💰 **Precio Estipulado:** ${precio_sociedad} USD\n"
            f"👤 **Usuario:** {display_name}\n"
            f"🆔 **ID del Usuario:** `{user_id}`\n"
            f"══════════════════\n"
            f"⚠️ Esta no es una recarga de saldo. Aprobar esto cambiará el rango de este usuario a 'socio'. Revisa el comprobante."
        )

        await context.bot.send_photo(chat_id=ADMIN_ID, photo=foto, caption=caption_admin, reply_markup=InlineKeyboardMarkup(teclado_admin), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error procesando comprobante VIP: {e}")
        await update_form(update, context, "❌ Ocurrió un error al cargar la imagen. Inténtalo de nuevo más tarde.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Menú", callback_data="menu_principal")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def buscar_user_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = update.message.text.strip().replace('@', '')
        u = db_query("SELECT * FROM usuarios WHERE user_id = ? OR username = ? OR telefono = ?", (uid, uid, uid), fetch=True)

        try: await update.message.delete()
        except: pass

        if not u:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No hemos detectado ningún usuario que coincida en nuestra base de datos central.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
            return ConversationHandler.END

        res_keys = db_query("SELECT COUNT(*) as c FROM keys WHERE comprador_id = ?", (u.get('user_id'),), fetch=True)
        keys = res_keys['c'] if res_keys else 0

        status_ban = "🔴 CUENTA SUSPENDIDA" if u.get('is_banned', 0) else "🟢 Operativo y Activo"
        btn_ban_lbl = "🔓 Reactivar Acceso a Cuenta" if u.get('is_banned', 0) else "🔨 Suspender Acceso a Cuenta"

        u_name = md_safe(u.get('username') if u.get('username') else "Sin_Nombre")
        u_tel = md_safe(u.get('telefono') if u.get('telefono') else "No_Proporcionado")
        u_rango = md_safe(u.get('rango', 'cliente')).upper()

        txt = f"🔎 **REPORTE MEGA DETALLADO DE CLIENTE**\n══════════════════\n🆔 ID Universal: `{u.get('user_id')}`\n👤 Tag de Usuario: {u_name}\n📱 Número Móvil: {u_tel}\n🌟 Nivel de Privilegios: **{u_rango}**\n💰 Capital Actual: **${u.get('saldo', 0.0):.2f} USD**\n🔥 **TOTAL INVERTIDO EN TIENDA:** **${u.get('total_gastado', 0.0):.2f} USD**\n🔑 Licencias Adquiridas: {keys} Unidades\n⚠️ Estado General: **{status_ban}**\n══════════════════"

        btns = [
            [InlineKeyboardButton("📜 Historial de Recargas", callback_data=f"adm_uhist_rec_{u.get('user_id')}_0")],
            [InlineKeyboardButton("🔑 Historial de Claves y Productos", callback_data=f"adm_uhist_key_{u.get('user_id')}_0")],
            [InlineKeyboardButton("Ascender a Nivel Socio VIP", callback_data=f"adm_rango_{u.get('user_id')}_socio"), InlineKeyboardButton("Degradar a Cliente", callback_data=f"adm_rango_{u.get('user_id')}_cliente")],
            [InlineKeyboardButton(btn_ban_lbl, callback_data=f"adm_togban_{u.get('user_id')}")],
            [InlineKeyboardButton("🏠 Regresar al Panel de Control", callback_data="adm_panel")]
        ]

        await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error en buscar_user_save: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Ocurrió un error interno al leer el registro del cliente.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def buscar_key_admin_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        llave = update.message.text.strip()
        k = db_query("SELECT k.*, p.nombre as prod_nombre, d.dias as dur_dias FROM keys k JOIN duraciones d ON k.duracion_id = d.id JOIN productos p ON d.producto_id = p.id WHERE k.llave = ?", (llave,), fetch=True)

        try: await update.message.delete()
        except: pass

        if not k:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ No se encontró ninguna llave con ese registro en la base de datos.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
            return ConversationHandler.END

        estado_venta = "Vendida" if k['vendida'] == 1 else ("Reemplazada/Anulada" if k['vendida'] == 2 else "En Stock (No vendida)")

        txt = f"🔎 **REPORTE DE CLAVE (KEY)**\n══════════════════\n🔑 **Key:** `{k['llave']}`\n📦 **Producto:** {md_safe(k.get('prod_nombre'))}\n⏳ **Duración Oficial:** {k.get('dur_dias')} Días\n📌 **Estado Actual:** {estado_venta}\n\n"

        if k['vendida'] == 1:
            u = db_query("SELECT username, user_id FROM usuarios WHERE user_id = ?", (k['comprador_id'],), fetch=True)
            u_str = f"@{u['username']} (`{u['user_id']}`)" if u else f"`{k['comprador_id']}`"
            txt += f"👤 **Comprador:** {md_safe(u_str)}\n"
            txt += f"📅 **Fecha de Compra:** {k['fecha_compra']} UTC\n"
            tiempo_rest = calcular_tiempo_restante(k['fecha_compra'], k['dur_dias'])
            txt += f"⏱️ **Tiempo de Uso Restante:** **{tiempo_rest}**\n"

        txt += "══════════════════"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=txt, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))

    except Exception as e:
        logger.error(f"Error en buscar_key_admin_save: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Ocurrió un error interno al leer el registro de esta credencial.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def reemplazar_key_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mala = update.message.text.strip()
        old_k = db_query("SELECT * FROM keys WHERE llave = ?", (mala,), fetch=True)
        if not old_k or old_k.get('vendida') == 0:
            await update_form(update, context, "❌ El registro informático indica que esta credencial (key) no ha sido reportada como vendida o no existe.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
            return ConversationHandler.END

        new_k = db_query("SELECT * FROM keys WHERE duracion_id = ? AND vendida = 0 LIMIT 1", (old_k.get('duracion_id'),), fetch=True)
        if not new_k:
            await update_form(update, context, "❌ Fallo en la reposición de garantía. El inventario actual está vacío, por favor inyecta nuevas licencias al sistema para poder reemplazarla.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
            return ConversationHandler.END

        db_query("UPDATE keys SET vendida = 2 WHERE id = ?", (old_k.get('id'),))
        db_query("UPDATE keys SET vendida = 1, comprador_id = ?, fecha_compra = CURRENT_TIMESTAMP WHERE id = ?", (old_k.get('comprador_id'), new_k.get('id')))

        try:
            await context.bot.send_message(old_k.get('comprador_id'), f"🔄 **RESOLUCIÓN APROBADA DE GARANTÍA**\nHemos analizado tu caso reportado. Lamentamos profundamente el inconveniente causado, aquí te proveemos una nueva licencia funcional de reemplazo:\n\n`{new_k.get('llave')}`", parse_mode='Markdown')
        except: pass

        await update_form(update, context, f"✅ Garantía ejecutada exitosamente. La nueva credencial despachada al cliente es: `{new_k.get('llave')}`", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    except Exception as e:
        logger.error(f"Error reemplazando key: {e}")
        await update_form(update, context, "❌ Conflicto lógico de base de datos, operación cancelada.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def admin_saldo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        identificador, monto = update.message.text.split(maxsplit=1)
        identificador = identificador.replace('@', '')
        monto_f = float(monto)

        u = db_query("SELECT user_id FROM usuarios WHERE user_id = ? OR telefono = ? OR username = ?", (identificador, identificador, identificador), fetch=True)

        if u:
            # SI SE LE ASIGNA SALDO POSITIVO DE MANERA MANUAL, LO CONTABILIZAMOS EN SU HISTORIAL DE RECARGAS PERO NUNCA EN TOTAL GASTADO
            db_query("UPDATE usuarios SET saldo = saldo + ? WHERE user_id = ?", (monto_f, u.get('user_id')))
            if monto_f > 0:
                db_query("INSERT INTO historial_recargas (user_id, monto, moneda, pais) VALUES (?, ?, ?, ?)", (u.get('user_id'), monto_f, "USD", "CARGA MANUAL ADMIN"))
                
                # ETIQUETADO AUTOMÁTICO DE SOCIOS (PUNTO B)
                etiqueta_red = registrar_recarga_etiquetada(u.get('user_id'), monto_f, "USD", "CARGA MANUAL ADMIN", "Manual")
                if etiqueta_red:
                    try: await context.bot.send_message(chat_id=update.effective_chat.id, text=f"🏷️ **DETALLE ETIQUETADO DE RED:**{etiqueta_red}", parse_mode='Markdown')
                    except: pass

            if monto_f > 0:
                try: await context.bot.send_message(chat_id=u.get('user_id'), text=f"💰 **¡FONDOS ASIGNADOS!**\nUn administrador ha depositado **${monto_f:.2f} USD** directamente en tu cuenta de forma manual. ¡Aprovecha para comprar!", parse_mode='Markdown')
                except: pass
            else:
                try: await context.bot.send_message(chat_id=u.get('user_id'), text=f"📉 **ACTUALIZACIÓN BANCARIA DE SALDO**\nSe ha realizado un ajuste contable en tu cuenta equivalente a **${monto_f:.2f} USD**.", parse_mode='Markdown')
                except: pass

            await update_form(update, context, f"✅ Balance contable del ID `{identificador}` actualizado con éxito en la base de datos.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
        else:
            await update_form(update, context, "❌ Usuario no encontrado en los registros. Revisa el ID.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))

    except Exception as e:
        logger.error(f"Error modificando saldo: {e}")
        await update_form(update, context, "❌ Fallo sintáctico. Recuerda respetar la plantilla dictada: `ID Monto`", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def config_simple_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        est = context.user_data.get('conv_estado_real')
        val = update.message.text.strip() if update.message.text else ""
        if update.message.photo:
            val = update.message.photo[-1].file_id
        if val == '0':
            val = ""

        if est == EDIT_PRECIO:
            partes = val.replace('$', '').replace(' ', '').split(',')
            p_cli = float(partes[0])
            if len(partes) > 1: db_query("UPDATE duraciones SET precio = ?, precio_socio = ? WHERE id = ?", (p_cli, float(partes[1]), context.user_data['tmp_dur_id']))
            else: db_query("UPDATE duraciones SET precio = ? WHERE id = ?", (p_cli, context.user_data['tmp_dur_id']))
        elif est == OFERTA_PRECIO:
            oferta_val = float(val)
            db_query("UPDATE duraciones SET precio_oferta = ?, en_oferta = ? WHERE id = ?", (oferta_val, 1 if oferta_val > 0 else 0, context.user_data['tmp_dur_id']))

            if oferta_val > 0:
                d_info = db_query("SELECT p.nombre FROM duraciones d JOIN productos p ON d.producto_id = p.id WHERE d.id = ?", (context.user_data['tmp_dur_id'],), fetch=True)
                if d_info:
                    mensaje_oferta = f"🔥 **¡NUEVA OFERTA FLASH ACTIVADA!** 🔥\n\nEl codiciado producto **{md_safe(d_info.get('nombre'))}** acaba de bajar drásticamente de precio a solo **${oferta_val:.2f} USD**. \n¡Ingresa a la tienda VIP y aprovecha esta ganga antes de que se agote el inventario!"
                    asyncio.create_task(broadcast_background(context, mensaje_oferta))

        elif est == ADD_KEYS:
            with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
                c = conn.cursor()
                keys_to_insert = [(context.user_data['tmp_dur_id'], k.strip()) for k in val.split('\n') if k.strip()]
                c.executemany("INSERT INTO keys (duracion_id, llave) VALUES (?, ?)", keys_to_insert)
                conn.commit()
        elif est == ADD_LINK_DESC: db_query("UPDATE productos SET link_descarga = ? WHERE id = ?", (val, context.user_data['tmp_prod_id']))
        elif est == ADD_LINK_TUT: db_query("UPDATE productos SET link_tutorial = ? WHERE id = ?", (val, context.user_data['tmp_prod_id']))
        elif est == RENOMBRAR_PROD: db_query("UPDATE productos SET nombre = ? WHERE id = ?", (val, context.user_data['tmp_prod_id']))
        elif est == BORRAR_USER: db_query("DELETE FROM usuarios WHERE user_id = ?", (val,))
        elif est == EDIT_SOPORTE: db_query("UPDATE config SET valor = ? WHERE clave = 'link_soporte'", (val,))
        elif est == EDIT_CANAL: db_query("UPDATE config SET valor = ? WHERE clave = 'link_canal'", (val,))
        elif est == EDIT_BANNER: db_query("UPDATE config SET valor = ? WHERE clave = 'banner_url'", (val,))
        elif est == EDIT_IMG_REG: db_query("UPDATE config SET valor = ? WHERE clave = 'imagen_registro'", (val,))
        elif est == EDIT_IMG_PJ: db_query("UPDATE proyectos SET imagen = ? WHERE id = ?", (val, context.user_data['tmp_pj_id']))
        elif est == EDIT_IMG_PD: db_query("UPDATE productos SET imagen = ? WHERE id = ?", (val, context.user_data['tmp_pd_id']))
        elif est == EDIT_METODOS: db_query("UPDATE config SET valor = ? WHERE clave = 'link_recargas'", (val,))
        elif est == CFG_DESC_SOCIO: db_query("UPDATE config SET valor = ? WHERE clave = 'desc_socio'", (val,))
        elif est == CFG_COM_REF: db_query("UPDATE config SET valor = ? WHERE clave = 'comision_ref'", (val,))
        elif est == EDIT_PRECIO_SOCIEDAD: db_query("UPDATE config SET valor = ? WHERE clave = 'precio_sociedad'", (val,))
        elif est == EDIT_PAIS_TASA: db_query("UPDATE metodos_pais SET tasa = ? WHERE pais = ?", (float(val), context.user_data['tmp_pais']))
        elif est == EDIT_PAIS_DET: db_query("UPDATE metodos_pais SET detalles = ? WHERE pais = ?", (val, context.user_data['tmp_pais']))

        await update_form(update, context, "✅ Todos los cambios fueron alojados y encriptados exitosamente en la base de datos.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Regresar al Panel de Control", callback_data="adm_panel")]]))
    except Exception as e:
        logger.error(f"Error Guardado Simple: {e}")
        await update_form(update, context, "❌ El sistema ha rechazado tu orden a causa de un formato de texto inválido.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Regresar al Panel de Control", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def wrapper_cfg(update: Update, context: ContextTypes.DEFAULT_TYPE, estado):
    context.user_data['conv_estado_real'] = estado
    return await config_simple_save(update, context)

async def add_pais_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        p = update.message.text.split(",")
        context.user_data['tmp_p'] = p[0].strip()
        context.user_data['tmp_b'] = p[1].strip()
        context.user_data['tmp_m'] = p[2].strip()
        await update_form(update, context, f"💵 Por favor escribe la **TASA DE CAMBIO** y los **DETALLES DE CUENTAS BANCARIAS** divididos rigurosamente por una coma `,`\n(Ej: `17.5,Transferencia SPEI clabe: 123 Banco: Azteca`)", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return ADD_PAIS_DATOS
    except Exception:
        await update_form(update, context, "❌ Estructura de texto incorrecta. Recuerda usar estrictamente las comas `,` para delimitar la información que pones.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def add_pais_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        p = update.message.text.split(",", 1)
        db_query("INSERT INTO metodos_pais VALUES (?, ?, ?, ?, ?)", (context.user_data['tmp_p'], context.user_data['tmp_b'], context.user_data['tmp_m'], float(p[0]), p[1].strip()))
        await update_form(update, context, "✅ Nueva región de pago configurada y activada satisfactoriamente para los usuarios.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
    except Exception:
        await update_form(update, context, "❌ Falla de procesamiento al intentar registrar los detalles de la cuenta. Intenta de nuevo.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def pkg_proj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['n_proj'] = update.message.text.strip()
        await update_form(update, context, "2️⃣ A continuación, escribe el titular del ARTÍCULO o Producto que estará dentro de la Categoría:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return CREAR_PAQUETE_PROD
    except Exception:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def pkg_prod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['n_prod'] = update.message.text.strip()
        await update_form(update, context, "3️⃣ Asigna las DURACIONES Y COSTOS del artículo.\nEstructura requerida estrictamente: `Dias,PrecioCliente,PrecioVIP`\n(Ejemplo: `30, 15.50, 10.00`):", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return CREAR_PAQUETE_DUR
    except Exception:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def pkg_dur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datos = update.message.text.strip().split('\n')
        duraciones_a_insertar = []
        for l in datos:
            partes = l.replace('$', '').replace(' ', '').split(',')
            if len(partes) >= 2:
                duraciones_a_insertar.append((int(partes[0]), float(partes[1]), float(partes[2]) if len(partes) >= 3 else 0.0))

        if not duraciones_a_insertar:
            raise ValueError("Cifras no válidas.")

        with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO proyectos (nombre) VALUES (?)", (context.user_data['n_proj'],))
            pj = cursor.lastrowid
            cursor.execute("INSERT INTO productos (proyecto_id, nombre) VALUES (?, ?)", (pj, context.user_data['n_prod']))
            pd = cursor.lastrowid
            for d, pc, ps in duraciones_a_insertar:
                cursor.execute("INSERT INTO duraciones (producto_id, dias, precio, precio_socio) VALUES (?, ?, ?, ?)", (pd, d, pc, ps))
            conn.commit()
        await update_form(update, context, "✅ ¡Felicidades! El nuevo Paquete de Ventas ha sido publicado en el catálogo público.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    except Exception as e:
        logger.error(f"Error creando paquete: {e}")
        await update_form(update, context, "❌ Anomalía detectada con los precios o números de días proporcionados. Corrige la escritura e intenta de nuevo.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def add_prod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['n_prod'] = update.message.text.strip()
        await update_form(update, context, "⏱️ Asigna las DURACIONES Y COSTOS que tendrá este nuevo producto.\nEstructura requerida: `Dias,PrecioCliente,PrecioVIP`\n(Ejemplo: `30, 15.50, 10.00`):", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return ADD_PROD_DUR
    except Exception:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def add_prod_dur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datos = update.message.text.strip().split('\n')
        duraciones_a_insertar = []
        for l in datos:
            partes = l.replace('$', '').replace(' ', '').split(',')
            if len(partes) >= 2:
                duraciones_a_insertar.append((int(partes[0]), float(partes[1]), float(partes[2]) if len(partes) >= 3 else 0.0))

        if not duraciones_a_insertar: raise ValueError("Parámetro inválido.")

        with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO productos (proyecto_id, nombre) VALUES (?, ?)", (context.user_data['tmp_proj_id'], context.user_data['n_prod']))
            pd = cursor.lastrowid
            for d, pc, ps in duraciones_a_insertar:
                cursor.execute("INSERT INTO duraciones (producto_id, dias, precio, precio_socio) VALUES (?, ?, ?, ?)", (pd, d, pc, ps))
            conn.commit()
        await update_form(update, context, "✅ El artículo ha sido insertado correctamente y ya es visible en el catálogo oficial.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    except Exception as e:
        logger.error(f"Error agregando duraciones de producto: {e}")
        await update_form(update, context, "❌ Ocurrió un bloqueo algorítmico al intentar interpretar las cantidades numéricas que pusiste.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def add_dur_dur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datos = update.message.text.strip().split('\n')
        duraciones_a_insertar = []
        for l in datos:
            partes = l.replace('$', '').replace(' ', '').split(',')
            if len(partes) >= 2:
                duraciones_a_insertar.append((int(partes[0]), float(partes[1]), float(partes[2]) if len(partes) >= 3 else 0.0))

        if not duraciones_a_insertar: raise ValueError("Letras no permitidas")

        with sqlite3.connect(DB_NAME, timeout=20.0) as conn:
            cursor = conn.cursor()
            for d, pc, ps in duraciones_a_insertar:
                cursor.execute("INSERT INTO duraciones (producto_id, dias, precio, precio_socio) VALUES (?, ?, ?, ?)", (context.user_data['tmp_prod_id'], d, pc, ps))
            conn.commit()
        await update_form(update, context, "✅ El nuevo tiempo de uso y precio se ha vinculado permanentemente al artículo.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
    except Exception as e:
        logger.error(f"Error agregando duración: {e}")
        await update_form(update, context, "❌ Hubo un conflicto con la escritura de los costos. Recuerda digitar únicamente números enteros o decimales.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def cup_cod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['c_cod'] = update.message.text.strip().upper()
        await update_form(update, context, "💵 ¿Qué cantidad económica de saldo en USD se le regalará y acreditará al portador que use este código?", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return CREAR_CUPON_VAL
    except Exception:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def cup_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['c_val'] = float(update.message.text.strip())
        await update_form(update, context, "👥 Especifica la capacidad máxima (Límite) de usuarios/personas diferentes que podrán reclamar este cupón antes de que caduque:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return CREAR_CUPON_LIM
    except ValueError:
        await update_form(update, context, "❌ El sistema financiero rechaza esto. Solo se permiten cifras enteras o decimales puros (ej. `10.50`).", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def cup_lim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        limite = int(update.message.text.strip())
        db_query("INSERT INTO cupones (codigo, valor, limite) VALUES (?, ?, ?)", (context.user_data['c_cod'], context.user_data['c_val'], limite))
        await update_form(update, context, "✅ El bono promocional fue generado con éxito y ya está activo en el servidor para que los usuarios lo reclamen.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel de Control", callback_data="adm_panel")]]))
    except ValueError:
        await update_form(update, context, "❌ El límite total debe expresarse obligatoriamente con un número entero.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Panel Admin", callback_data="adm_panel")]]))
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def com_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['com_text'] = update.message.text
        await update_form(update, context, "📸 Por favor pasa la FOTOGRAFÍA del comunicado si lo requiere (Si quieres enviar puro texto, escribe el número `0`):", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return COM_PHOTO
    except Exception:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def com_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['com_pic'] = update.message.photo[-1].file_id if update.message.photo else None
        await update_form(update, context, "🔗 Proporciona el diseño del Botón que acompañará al mensaje (`Texto del Botón - Enlace Directo`) o manda un `0` para no usar botón:", InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar Operación", callback_data="cancelar_cb")]]))
        return COM_BTN
    except Exception:
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def com_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        t = update.message.text.strip()
        b = None
        if '-' in t and t != '0':
            n, url = t.split('-', 1)
            b = InlineKeyboardMarkup([[InlineKeyboardButton(n.strip(), url=url.strip())]])
        context.user_data['com_btn'] = b
        await update_form(update, context, "📢 Protocolo en posición y listo. ¿Autorizas ahora mismo el despliegue del envío masivo a toda tu base de datos?", InlineKeyboardMarkup([[InlineKeyboardButton("✅ SÍ, INICIAR TRANSMISIÓN MASIVA", callback_data="env_com"), InlineKeyboardButton("❌ Suspender Protocolo", callback_data="cancelar_cb")]]))
        return COM_BTN
    except Exception as e:
        logger.error(f"Error parseando boton: {e}")
        marcar_ocupado(context, False)
        return ConversationHandler.END

async def enviar_com_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        if query.data == "env_com":
            users = db_query("SELECT user_id FROM usuarios", fetchall=True)
            t = context.user_data.get('com_text', "Mensaje de Estado del Sistema:")
            p = context.user_data.get('com_pic')
            b = context.user_data.get('com_btn')

            await render_msg(query, context, "⏳ Repartiendo el boletín a toda la red de clientes... Por favor, no interrumpas la conexión ni toques nada.", InlineKeyboardMarkup([]))

            exito = 0
            for u in users:
                try:
                    if p: await context.bot.send_photo(u['user_id'], p, f"📢 **ANUNCIO OFICIAL**\n\n{t}", reply_markup=b, parse_mode='Markdown')
                    else: await context.bot.send_message(u['user_id'], f"📢 **ANUNCIO OFICIAL**\n\n{t}", reply_markup=b, parse_mode='Markdown')
                    exito += 1
                except: pass
                await asyncio.sleep(0.05)

            await render_msg(query, context, f"✅ Antena de difusión inactiva. El envío masivo ha culminado. Alcance verificado: {exito} clientes contactados.", InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Hub Central", callback_data="adm_panel")]]))
    except Exception as e:
        logger.error(f"Error enviando comunicado: {e}")
    finally:
        marcar_ocupado(context, False)
        return ConversationHandler.END

def main():
    inicializar_db()
    app = Application.builder().token(TOKEN).build()

    def photo_text_handler(estado_id):
        return MessageHandler(filters.TEXT | filters.PHOTO, lambda u,c: wrapper_cfg(u,c,estado_id))

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(conv_start_client, pattern="^(c_cupon|c_recm_|c_socp_|c_reccustom_|c_qtycustom_)"),
            CallbackQueryHandler(conv_start_admin, pattern="^(adm_crear_paquete|adm_addprod_|adm_adddur_|adm_renprod_|adm_buscar_usr|adm_dar_saldo|adm_comunicado|adm_crear_cupon|adm_borrar_usr|adm_reemplazar|adm_add_pais|adm_etasa_|adm_edet_|adm_edit_pr_|adm_oferta_|adm_add_key_|adm_linkdesc_|adm_linktut_|adm_edit_soporte|adm_edit_canal|adm_edit_banner|adm_edit_img_reg|adm_img_pj_|adm_img_pd_|adm_edit_rec|adm_cfg_dsoc|adm_cfg_cref|adm_cfg_psoc|adm_buscar_key_btn)")
        ],
        states={
            CANJEAR_CUPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, cl_cupon_save)],
            ENVIAR_COMPROBANTE: [MessageHandler(filters.PHOTO | filters.TEXT, cl_comprobante_save)],
            ENVIAR_COMP_SOCIEDAD: [MessageHandler(filters.PHOTO | filters.TEXT, cl_comprobante_soc_save)],
            CUSTOM_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, cl_custom_qty)],
            CUSTOM_RECARGA: [MessageHandler(filters.TEXT & ~filters.COMMAND, cl_custom_recarga)],
            CREAR_PAQUETE_PROJ: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_proj)],
            CREAR_PAQUETE_PROD: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_prod)],
            CREAR_PAQUETE_DUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, pkg_dur)],
            ADD_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_prod_name)],
            ADD_PROD_DUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_prod_dur)],
            ADD_DUR_DUR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_dur_dur)],
            DAR_SALDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_saldo_save)],
            BUSCAR_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_user_save)],
            BUSCAR_KEY_ADM: [MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_key_admin_save)],
            REEMPLAZAR_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, reemplazar_key_save)],
            ADD_PAIS_NOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pais_nom)],
            ADD_PAIS_DATOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pais_datos)],
            CREAR_CUPON_COD: [MessageHandler(filters.TEXT & ~filters.COMMAND, cup_cod)],
            CREAR_CUPON_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cup_val)],
            CREAR_CUPON_LIM: [MessageHandler(filters.TEXT & ~filters.COMMAND, cup_lim)],
            EDIT_PRECIO: [photo_text_handler(EDIT_PRECIO)],
            OFERTA_PRECIO: [photo_text_handler(OFERTA_PRECIO)],
            ADD_KEYS: [photo_text_handler(ADD_KEYS)],
            ADD_LINK_DESC: [photo_text_handler(ADD_LINK_DESC)],
            ADD_LINK_TUT: [photo_text_handler(ADD_LINK_TUT)],
            RENOMBRAR_PROD: [photo_text_handler(RENOMBRAR_PROD)],
            BORRAR_USER: [photo_text_handler(BORRAR_USER)],
            EDIT_SOPORTE: [photo_text_handler(EDIT_SOPORTE)],
            EDIT_CANAL: [photo_text_handler(EDIT_CANAL)],
            EDIT_METODOS: [photo_text_handler(EDIT_METODOS)],
            CFG_DESC_SOCIO: [photo_text_handler(CFG_DESC_SOCIO)],
            CFG_COM_REF: [photo_text_handler(CFG_COM_REF)],
            EDIT_PRECIO_SOCIEDAD: [photo_text_handler(EDIT_PRECIO_SOCIEDAD)],
            EDIT_PAIS_TASA: [photo_text_handler(EDIT_PAIS_TASA)],
            EDIT_PAIS_DET: [photo_text_handler(EDIT_PAIS_DET)],
            EDIT_BANNER: [photo_text_handler(EDIT_BANNER)],
            EDIT_IMG_REG: [photo_text_handler(EDIT_IMG_REG)],
            EDIT_IMG_PJ: [photo_text_handler(EDIT_IMG_PJ)],
            EDIT_IMG_PD: [photo_text_handler(EDIT_IMG_PD)],
            COM_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, com_text)],
            COM_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, com_photo)],
            COM_BTN: [MessageHandler(filters.TEXT & ~filters.COMMAND, com_btn), CallbackQueryHandler(enviar_com_final, pattern="^env_com$")]
        },
        fallbacks=[
            CallbackQueryHandler(cancelar_cb, pattern="^(cancelar_cb|menu_principal)$"),
            CommandHandler("start", cancel_and_start)
        ], allow_reentry=True)

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, recibir_contacto))
    app.add_handler(CallbackQueryHandler(menu_principal, pattern="^menu_principal$"))
    app.add_handler(CallbackQueryHandler(cliente_nav, pattern="^c_"))
    app.add_handler(CallbackQueryHandler(adm_nav, pattern="^adm_"))

    logger.info("🚀 SISTEMA CENTRAL INICIADO -> PRODUCCIÓN 24/7 (CERO ERRORES)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

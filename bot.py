import discord
from discord.ext import commands, tasks
import requests
import feedparser
from deep_translator import GoogleTranslator
import os

# ---------------------------
# CONFIGURACIÓN
# ---------------------------
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1475147737874956481  # Canal de noticias
WELCOME_CHANNEL_ID = 1476143363546812479  # Canal de bienvenida
AUTO_ROLE_ID = 1475146921281589298  # Rol automático

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------
# TRADUCTOR
# ---------------------------
def traducir(texto):
    try:
        return GoogleTranslator(source="auto", target="es").translate(texto)
    except:
        return texto

# ---------------------------
# OBTENER NOTICIAS (ANN)
# ---------------------------
def obtener_noticias_ann():
    feed = feedparser.parse("https://www.animenewsnetwork.com/news/rss.xml")
    noticias = []

    for entry in feed.entries[:5]:
        titulo = traducir(entry.title)
        resumen = traducir(entry.summary) if "summary" in entry else "Sin resumen disponible."
        link = entry.link

        noticias.append({
            "titulo": titulo,
            "resumen": resumen,
            "link": link
        })

    return noticias

# ---------------------------
# ANIList (comando !anime)
# ---------------------------
def buscar_anime_anilist(nombre):
    query = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        title { romaji }
        description(asHtml: false)
        siteUrl
      }
    }
    """
    variables = {"search": nombre}
    url = "https://graphql.anilist.co"
    response = requests.post(url, json={"query": query, "variables": variables})
    data = response.json()

    media = data["data"]["Media"]
    titulo = traducir(media["title"]["romaji"])
    descripcion = traducir(media["description"])
    url = media["siteUrl"]

    return titulo, descripcion, url

@bot.command()
async def anime(ctx, *, nombre):
    titulo, descripcion, url = buscar_anime_anilist(nombre)

    embed = discord.Embed(
        title=titulo,
        description=descripcion[:400] + "...",
        color=discord.Color.blue()
    )
    embed.add_field(name="Enlace", value=url)

    await ctx.send(embed=embed)

# ---------------------------
# SISTEMA ANTI-DUPLICADOS
# ---------------------------
def cargar_noticias_enviadas():
    if not os.path.exists("last_news.txt"):
        return set()
    with open("last_news.txt", "r", encoding="utf-8") as f:
        return set(line.strip() for line in f.readlines())

def guardar_noticias_enviadas(noticias):
    with open("last_news.txt", "a", encoding="utf-8") as f:
        for link in noticias:
            f.write(link + "\n")

# ---------------------------
# DETECTOR DE NOTICIAS GRANDES
# ---------------------------
PALABRAS_CLAVE_GRANDES = [
    "season", "temporada", "anime", "manga", "trailer", "announcement",
    "release", "live action", "movie", "film", "ova", "special",
    "naruto", "one piece", "bleach", "dragon ball", "jujutsu", "chainsaw",
    "attack on titan", "aot", "kimetsu", "demon slayer", "my hero"
]

def es_noticia_grande(titulo, resumen):
    texto = (titulo + " " + resumen).lower()
    return any(palabra in texto for palabra in PALABRAS_CLAVE_GRANDES)

# ---------------------------
# TAREA AUTOMÁTICA CADA 10 MINUTOS
# ---------------------------
@tasks.loop(minutes=10)
async def enviar_noticias():
    canal = bot.get_channel(CHANNEL_ID)
    noticias = obtener_noticias_ann()

    enviadas = cargar_noticias_enviadas()
    nuevas = []

    for n in noticias:
        if n["link"] not in enviadas:
            nuevas.append(n)

    if not nuevas:
        print("No hay noticias nuevas.")
        return

    for n in nuevas:
        titulo = n["titulo"]
        resumen = n["resumen"]
        link = n["link"]

        # Noticia grande
        if es_noticia_grande(titulo, resumen):
            embed = discord.Embed(
                title=f"🔥 {titulo}",
                description=resumen[:500] + "...",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url="https://i.imgur.com/0Zf1ZqC.png")
        else:
            embed = discord.Embed(
                title=titulo,
                description=resumen[:500] + "...",
                color=discord.Color.orange()
            )

        embed.add_field(name="Leer más", value=link)
        embed.set_footer(text="Fuente: Anime News Network")

        await canal.send(embed=embed)

    guardar_noticias_enviadas([n["link"] for n in nuevas])
    print(f"Enviadas {len(nuevas)} noticias nuevas.")

# ---------------------------
# EVENTO: NUEVO USUARIO
# ---------------------------
@bot.event
async def on_member_join(member):
    # Asignar rol
    try:
        rol = member.guild.get_role(AUTO_ROLE_ID)
        await member.add_roles(rol)
    except Exception as e:
        print(f"Error asignando rol: {e}")

    # Canal de bienvenida
    canal = member.guild.get_channel(WELCOME_CHANNEL_ID)

    embed = discord.Embed(
        title="🎉 ¡Bienvenido/a a la Zona Anime!",
        description=f"{member.mention}, nos alegra tenerte aquí.\n¡Disfruta del servidor!",
        color=discord.Color.green()
    )

    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.set_footer(text=f"Usuario número {len(member.guild.members)} del servidor")

    await canal.send(embed=embed)

# ---------------------------
# INICIO DEL BOT
# ---------------------------
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    await enviar_noticias()  # Envía noticias al iniciar
    enviar_noticias.start()  # Luego cada 10 minutos

bot.run(TOKEN)
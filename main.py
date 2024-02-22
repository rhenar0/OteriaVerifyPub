import threading

from discord import ui
import discord
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from discord.ext import commands
import sqlite3
import uuid
import re
from flask import Flask, redirect
from discord_webhook import DiscordWebhook

app = Flask(__name__)

with open('config.json') as f:
    config = json.load(f)

description = '''A bot for Oteria Confirmation Process'''
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class SlashBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix='/', intents=intents, description=description)

    async def setup_hook(self) -> None:
        self.tree.copy_global_to(guild=discord.Object(id=1131288634549620897))
        await self.tree.sync()

bot = SlashBot()

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    await bot.setup_hook()


def verif_email(email):
    pattern = r"@oteria\.fr$"
    if re.search(pattern, email):
        return True
    else:
        return False

@app.route('/verify/<uuid>')
async def verify(uuid):
    conn = sqlite3.connect('verif.db')
    c = conn.cursor()
    c.execute("SELECT * FROM verif WHERE GUID_verif = ?", (uuid,))
    data = c.fetchone()
    if data is None:
        return "Erreur : Ce lien n'est pas valide."
    elif data[3] == 1:
        return "Erreur : Ce lien a deja ete utilise."
    else:
        c.execute("UPDATE verif SET verified = 1 WHERE GUID_verif = ?", (uuid,))
        conn.commit()
        c.execute("SELECT * FROM verif WHERE GUID_verif = ?", (uuid,))
        datad = c.fetchone()
        webhook = DiscordWebhook(url="https://discord.com/api/webhooks/1131296698422010047/UHbTd42PIjc1I0O6jJw8Iw83T-C_jJpbQ3KhE1fwMp1VFlJnw6jGQXUAyGebfWGX-R6i", content="/accept " + datad[4] + " 4862fc26-b67b-4f29-9891-8058a7f4c3ac " + datad[5] + "")
        webhook.execute()
        return redirect("https://discord.com/channels/964988687660249179/1131288634549620897", code=302)

@bot.tree.command(name="verify", description="Permet de verifier que vous etes bien de chez Oteria.")
async def _verify(interaction: discord.Interaction) -> None:
    await interaction.response.send_modal(Questionnaire())


@bot.event
async def on_message(message):
    if message.channel.id == 1131288634549620897:
        if message.content.startswith("/accept"):
            parsed = message.content.split()
            user = bot.get_user(int(parsed[1]))
            user = await message.guild.fetch_member(user.id)
            role = discord.utils.get(message.guild.roles, name="en_attente_de_role")
            await user.add_roles(role)
            await user.edit(nick=f'{user.name} ({parsed[3]})')
            await message.channel.send(f'{user} a bien ete accepte !')


class Questionnaire(ui.Modal, title='Verification Oteria'):
    name = ui.TextInput(label='Prenom', placeholder='John')
    answer = ui.TextInput(label='Mail', placeholder='john.pounia@oteria.fr')

    async def on_submit(self, interaction: discord.Interaction):

        conn = sqlite3.connect('verif.db')
        c = conn.cursor()

        if self.answer.value == "":
            await interaction.response.send_message(f'Vous devez renseigner un mail.', ephemeral=True)
            return
        elif self.name.value == "":
            await interaction.response.send_message(f'Vous devez renseigner un prenom.', ephemeral=True)
            return
        elif not verif_email(self.answer.value):
            await interaction.response.send_message(f'Vous devez renseigner un mail Oteria.', ephemeral=True)
            return
        else:
            c.execute("CREATE TABLE IF NOT EXISTS verif (id INTEGER PRIMARY KEY AUTOINCREMENT, mail TEXT, GUID_verif TEXT, verified INTEGER, discordid TEXT, name TEXT)")
            conn.commit()
            c.execute("SELECT * FROM verif WHERE mail = ?", (self.answer.value,))
            data = c.fetchone()
            if data is not None:
                await interaction.response.send_message(f'Ce mail est deja utilise.', ephemeral=True)
                return

        myuuid = uuid.uuid4()

        c.execute("CREATE TABLE IF NOT EXISTS verif (id INTEGER PRIMARY KEY AUTOINCREMENT, mail TEXT, GUID_verif TEXT, verified INTEGER, discordid TEXT, name TEXT)")
        conn.commit()
        c.execute("INSERT INTO verif (mail, GUID_verif, verified, discordid, name) VALUES (?, ?, ?, ?, ?)", (self.answer.value, str(myuuid), 0, interaction.user.id, self.name.value))
        conn.commit()
        conn.close()

        msg = MIMEMultipart()
        msg['From'] = "no-reply@oteria.fr"
        msg['To'] = self.answer.value
        msg['Subject'] = "Confirmation de votre compte Oteria"
        message = "Bonjour " + self.name.value + ",\n\nMerci de ton inscription sur notre Discord.\n\nDerniere étape : Verifier ton adresse mail. \nIl suffit de cliquer ici : http://167.71.43.194:6969/verify/" + str(myuuid) + "\n\nCordialement,\n\nL'equipe du Discord Oteria"
        msg.attach(MIMEText(message))

        smtpObj = smtplib.SMTP('smtp-relay.sendinblue.com', 587)
        smtpObj.login('hugo.chassaing@oteria.fr', '')
        smtpObj.sendmail('no-reply@oteria.fr', self.answer.value, msg.as_string())
        smtpObj.quit()
        print("Successfully sent email")

        await interaction.response.send_message(f'Merci pour ta reponse, {self.name} ! Tu vas bientot recevoir un mail.', ephemeral=True)



threading.Thread(target=lambda: app.run(host='0.0.0.0', port=6969)).start()
bot.run(config['d_token'])
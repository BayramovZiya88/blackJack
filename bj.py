import discord
from discord.ext import commands
import json
import datetime
import random
import os

# Discord Intents'lerini ayarlama
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Botun prefix'ini (komut ön eki) ayarla
bot = commands.Bot(command_prefix='bj!', intents=intents)

# --- Veri Depolama Fonksiyonları ---
COIN_FILE = 'coins.json'

def load_data():
    """Verileri dosyadan yükler."""
    try:
        with open(COIN_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    """Verileri dosyaya kaydeder."""
    with open(COIN_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Blackjack Yardımcı Fonksiyonları ---

def create_deck():
    """52 kartlık bir deste oluşturur ve karıştırır."""
    suits = ['♠️', '♥️', '♦️', '♣️']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [{'rank': rank, 'suit': suit} for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

def calculate_hand_value(hand):
    """Bir eldeki kartların toplam değerini hesaplar."""
    value = 0
    num_aces = 0
    for card in hand:
        rank = card['rank']
        if rank in ['J', 'Q', 'K']:
            value += 10
        elif rank == 'A':
            num_aces += 1
            value += 11
        else:
            value += int(rank)
    
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
    return value

# --- Blackjack Oyunu Butonları ve Mantığı ---

class BlackjackView(discord.ui.View):
    def __init__(self, author, bet_amount):
        super().__init__(timeout=120.0)
        self.author = author
        self.bet_amount = bet_amount
        self.deck = create_deck()
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.message = None
        self.game_over = False

    def get_card_emojis(self, hand, hide_dealer_card=False):
        emojis = []
        for i, card in enumerate(hand):
            if hide_dealer_card and i == 0:
                emojis.append("🟫") 
            else:
                emojis.append(f"{card['rank']}{card['suit']}")
        return " ".join(emojis)

    def create_embed(self, game_over=False):
        embed = discord.Embed(title="Blackjack Oyunu", color=discord.Color.green())
        
        player_cards_emoji = self.get_card_emojis(self.player_hand)
        player_score = calculate_hand_value(self.player_hand)
        embed.add_field(name=f"Senin Elin ({player_score})", value=player_cards_emoji, inline=False)
        
        dealer_cards_emoji = self.get_card_emojis(self.dealer_hand, hide_dealer_card=not game_over)
        dealer_score_text = calculate_hand_value(self.dealer_hand) if game_over else "?"
        embed.add_field(name=f"Krupiyerin Eli ({dealer_score_text})", value=dealer_cards_emoji, inline=False)
        
        return embed

    def end_game(self):
        """Butonları devre dışı bırakır."""
        self.game_over = True
        for item in self.children:
            item.disabled = True
        self.stop()

    async def dealer_turn(self, interaction: discord.Interaction):
        """Krupiyerin hamlelerini yönetir."""
        while calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())
        
        await self.determine_winner(interaction)

    async def determine_winner(self, interaction: discord.Interaction):
        """Kazananı belirler ve coinleri günceller."""
        self.end_game()
        player_score = calculate_hand_value(self.player_hand)
        dealer_score = calculate_hand_value(self.dealer_hand)
        
        data = load_data()
        user_data = data.get(str(self.author.id), {"coins": 0})
        
        result = ""
        
        if player_score > 21:
            # Oyuncu 21'i geçti (Bust)
            result = f"Senin elin 21'i geçti! Kaybettin. Kaybedilen: **{self.bet_amount} coin**."
            # Bahis zaten oyunun başında düşürüldüğü için burada bir işlem yapmaya gerek yok.
        elif dealer_score > 21:
            # Krupiyer 21'i geçti
            result = f"Krupiyerin eli 21'i geçti! Kazandın. Kazanılan: **{self.bet_amount} coin**."
            user_data["coins"] += self.bet_amount * 2
        elif player_score > dealer_score:
            # Oyuncu kazandı
            result = f"Sen kazandın! Kazanılan: **{self.bet_amount} coin**."
            user_data["coins"] += self.bet_amount * 2
        elif dealer_score > player_score:
            # Krupiyer kazandı
            result = f"Krupiyer kazandı! Kaybettin. Kaybedilen: **{self.bet_amount} coin**."
            # Bahis zaten düşürüldüğü için burada bir işlem yapmaya gerek yok.
        else:
            # Berabere (Push)
            result = "Berabere (Push)! Bahis geri iade edildi."
            user_data["coins"] += self.bet_amount
        
        # Verileri kaydet
        data[str(self.author.id)] = user_data
        save_data(data)
        
        embed = self.create_embed(game_over=True)
        embed.add_field(name="Oyun Sona Erdi", value=result, inline=False)
        embed.set_footer(text=f"Güncel bakiyen: {user_data['coins']} coin")
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Kart Çek", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        """'Kart Çek' butonuna tıklandığında çalışır."""
        if interaction.user != self.author:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return

        self.player_hand.append(self.deck.pop())
        player_score = calculate_hand_value(self.player_hand)

        if player_score >= 21:
            self.end_game()
            await self.determine_winner(interaction)
        else:
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Dur", style=discord.ButtonStyle.danger, emoji="🛑")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        """'Dur' butonuna tıklandığında çalışır."""
        if interaction.user != self.author:
            await interaction.response.send_message("Bu senin oyunun değil!", ephemeral=True)
            return

        self.end_game()
        await self.dealer_turn(interaction)

# --- Bot Olayları ve Komutları ---

@bot.event
async def on_ready():
    """Botun hazır olduğunu bildiren olay."""
    print(f'Bot olarak giriş yapıldı: {bot.user.name}')
    print('------')

@bot.command(name='bakiye')
async def bakiye(ctx):
    """Kullanıcının coin bakiyesini gösterir."""
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = data.get(user_id, {"coins": 0})
    await ctx.send(f"💸 **{ctx.author.name}**, mevcut coin bakiyen: **{user_data['coins']}**")

@bot.command(name='daily')
async def daily(ctx):
    """Her gün bir kez 1000 coin verir."""
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = data.get(user_id, {"last_claimed": None, "coins": 0})
    
    today = datetime.date.today()
    last_claimed_date_str = user_data["last_claimed"]
    last_claimed_date = None
    if last_claimed_date_str:
        last_claimed_date = datetime.date.fromisoformat(last_claimed_date_str)

    if not last_claimed_date or last_claimed_date < today:
        user_data["coins"] += 1000
        user_data["last_claimed"] = str(today)
        data[user_id] = user_data
        save_data(data)
        await ctx.send(f"🎉 **{ctx.author.name}**, günlük 1000 coin ödülünü aldın! Toplam coin'in: **{user_data['coins']}**")
    else:
        await ctx.send(f"⏳ **{ctx.author.name}**, günlük ödülünü zaten aldın. Yarın tekrar dene!")

@bot.command(name='oyna')
async def oyna(ctx, bet: int):
    """Blackjack oyununu başlatır. Kullanım: bj!oyna <bahis_miktarı>"""
    user_id = str(ctx.author.id)
    data = load_data()
    user_data = data.get(user_id, {"coins": 0})
    
    if bet <= 0:
        await ctx.send("Lütfen geçerli bir bahis miktarı girin.")
        return
        
    if user_data["coins"] < bet:
        await ctx.send(f"Yeterli coin'in yok! Mevcut bakiyen: **{user_data['coins']}** coin.")
        return
        
    user_data["coins"] -= bet
    save_data(data)

    view = BlackjackView(ctx.author, bet)
    embed = view.create_embed()
    message = await ctx.send(f"{ctx.author.mention} Blackjack oyunu başladı!", embed=embed, view=view)
    view.message = message

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        if ctx.command.name == 'oyna':
            await ctx.send("Lütfen bir bahis miktarı belirtin! Örneğin: `bj!oyna 100`")
        else:
            await ctx.send(f"Komutu yanlış kullandın. `{error.param.name}` parametresi eksik.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Geçersiz bir değer girdin. Lütfen bir sayı girmeyi dene.")

# Botu token ile çalıştırma
# Lütfen TOKENİNİ tırnak işaretlerinin içine yapıştır

bot_token = os.environ.get("BOT_TOKEN")
if bot_token:
    bot.run(bot_token)
else:
    print("HATA: BOT_TOKEN ortam değişkeni bulunamadı.")



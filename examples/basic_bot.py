import qq
from qq.ext import commands
import random

intents = qq.Intents.default()

bot = commands.Bot(command_prefix='?', intents=intents)  # 注册机器人前缀为 ?


@bot.event
async def on_ready():  # 注册 on_ready 事件
    print(f'以 {bot.user} 身份登录（ID：{bot.user.id}）')
    print('------')


@bot.command()  # 注册指令 '?add'， 参数为 left right
async def add(ctx, left: int, right: int):
    """将两个数字相加。"""
    await ctx.reply(left + right)  # 发送 left + right的结果


@bot.command()  # 注册指令 '?roll', 参数为 dice
async def roll(ctx, dice: str):
    """以 NdN 格式掷骰子。"""
    try:
        rolls, limit = map(int, dice.split('d'))  # 判断格式是不是 NdN
    except Exception:
        await ctx.reply('格式必须是 NdN！')
        return

    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await ctx.reply(result)


@bot.command(description='当你有选择困难症')  # 注册指令 '?choose', 参数为多个choices， 例如 ?choose a b，choose会是['a', 'b']
async def choose(ctx, *choices: str):
    """在多个选项之间进行选择。"""
    await ctx.reply(random.choice(choices))  # 发送从 List 中随机选择一个


@bot.command()  # 注册指令 '?repeat', 参数为 time content, content 默认值为 重复...
async def repeat(ctx, times: int, content='重复...'):
    """多次重复一条消息。"""
    for i in range(times):  # 重复 time 次
        await ctx.reply(content)  # 发送 content


@bot.group()
async def cool(ctx):
    """说用户是否很酷。

     实际上，这只是检查是否正在调用子命令。
    """
    if ctx.invoked_subcommand is None:
        await ctx.reply(f'不，{ctx.subcommand_passed} 不牛逼')


@cool.command(name='bot')
async def _bot(ctx):
    """机器人牛逼吗？"""
    await ctx.reply('是的，机器人很牛逼。')


bot.run('token')

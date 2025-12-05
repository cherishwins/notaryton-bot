"""
MemeSeal TON - Internationalization (i18n)
Multi-language support: English, Russian, Chinese
"""

# User language cache (user_id -> lang_code)
user_languages = {}

TRANSLATIONS = {
    "en": {
        "welcome": "🔐 **NotaryTON** - Blockchain Notarization\n\nSeal contracts, files, and screenshots on TON forever.\n\n**Commands:**\n/notarize - Seal a contract\n/status - Check your subscription\n/subscribe - Get unlimited seals\n/referral - Earn 5% commission\n/withdraw - Withdraw referral earnings\n/lang - Change language",
        "no_sub": "⚠️ **Payment Required**\n\n1 Star or 0.015 TON to seal this.",
        "sealed": "✅ **SEALED ON TON!**\n\nHash: `{hash}`\n\n🔗 Verify: {url}\n\nProof secured forever! 🔒",
        "withdraw_success": "✅ **Withdrawal Sent!**\n\n{amount} TON sent to your wallet.\nTX will appear in ~30 seconds.",
        "withdraw_min": "⚠️ Minimum withdrawal: 0.05 TON\n\nYour balance: {balance} TON",
        "withdraw_no_wallet": "⚠️ Please send your TON wallet address first.\n\nExample: `EQB...` or `UQA...`",
        "lang_changed": "✅ Language changed to English",
        "referral_stats": "🎁 **Referral Program**\n\n**Your Link:**\n`{url}`\n\n**Commission:** 5%\n**Referrals:** {count}\n**Earnings:** {earnings} TON\n**Withdrawn:** {withdrawn} TON\n**Available:** {available} TON\n\n💡 Use /withdraw to cash out!",
        "status_active": "✅ **Subscription Active**\n\nExpires: {expiry}\n\nUnlimited seals enabled!",
        "status_inactive": "❌ **No Active Subscription**\n\nCredits: {credits} TON\n\nUse /subscribe for unlimited!",
        "photo_prompt": "📸 **Nice screenshot!**\n\n1 Star to seal it on TON forever.",
        "file_prompt": "📄 **Got your file!**\n\n1 Star to seal it on TON forever.",
        "sealing_progress": "⏳ **SEALING TO BLOCKCHAIN...**\n\nYour file is being timestamped on TON.\nThis takes 5-15 seconds.",
        "network_busy": "⚠️ **TON Network Busy**\n\nWe're retrying automatically. Please wait.",
        "retry_prompt": "🔄 **Try Again**\n\nTap the button below to retry.",
        "lottery_tickets": "🎫 Lottery tickets: {count}",
        "pot_grew": "💰 Pot grew +{amount} TON",
        "good_luck": "🍀 Good luck on Sunday!",
    },
    "ru": {
        "welcome": "🔐 **NotaryTON** - Блокчейн Нотаризация\n\nПечать контрактов, файлов и скриншотов на TON навсегда.\n\n**Команды:**\n/notarize - Запечатать контракт\n/status - Проверить подписку\n/subscribe - Безлимит\n/referral - Заработай 5%\n/withdraw - Вывести заработок\n/lang - Сменить язык",
        "no_sub": "⚠️ **Требуется оплата**\n\n1 Звезда или 0.015 TON для печати.",
        "sealed": "✅ **ЗАПЕЧАТАНО НА TON!**\n\nХеш: `{hash}`\n\n🔗 Проверить: {url}\n\nДоказательство сохранено навсегда! 🔒",
        "withdraw_success": "✅ **Вывод отправлен!**\n\n{amount} TON отправлено на ваш кошелек.\nTX появится через ~30 секунд.",
        "withdraw_min": "⚠️ Минимальный вывод: 0.05 TON\n\nВаш баланс: {balance} TON",
        "withdraw_no_wallet": "⚠️ Сначала отправьте адрес вашего TON кошелька.\n\nПример: `EQB...` или `UQA...`",
        "lang_changed": "✅ Язык изменен на Русский",
        "referral_stats": "🎁 **Реферальная Программа**\n\n**Ваша ссылка:**\n`{url}`\n\n**Комиссия:** 5%\n**Рефералы:** {count}\n**Заработано:** {earnings} TON\n**Выведено:** {withdrawn} TON\n**Доступно:** {available} TON\n\n💡 Используйте /withdraw для вывода!",
        "status_active": "✅ **Подписка Активна**\n\nИстекает: {expiry}\n\nБезлимитные печати включены!",
        "status_inactive": "❌ **Нет Активной Подписки**\n\nКредиты: {credits} TON\n\nИспользуйте /subscribe для безлимита!",
        "photo_prompt": "📸 **Отличный скриншот!**\n\n1 Звезда чтобы запечатать на TON навсегда.",
        "file_prompt": "📄 **Файл получен!**\n\n1 Звезда чтобы запечатать на TON навсегда.",
        "sealing_progress": "⏳ **ЗАПЕЧАТЫВАНИЕ В БЛОКЧЕЙН...**\n\nВаш файл получает временную метку на TON.\nЭто занимает 5-15 секунд.",
        "network_busy": "⚠️ **Сеть TON занята**\n\nМы автоматически повторяем. Пожалуйста, подождите.",
        "retry_prompt": "🔄 **Попробовать снова**\n\nНажмите кнопку ниже для повтора.",
        "lottery_tickets": "🎫 Лотерейные билеты: {count}",
        "pot_grew": "💰 Банк вырос на +{amount} TON",
        "good_luck": "🍀 Удачи в воскресенье!",
    },
    "zh": {
        "welcome": "🔐 **NotaryTON** - 区块链公证\n\n在TON上永久封存合约、文件和截图。\n\n**命令:**\n/notarize - 封存合约\n/status - 查看订阅\n/subscribe - 无限封存\n/referral - 赚取5%佣金\n/withdraw - 提取收益\n/lang - 更改语言",
        "no_sub": "⚠️ **需要付款**\n\n1星或0.015 TON来封存。",
        "sealed": "✅ **已封存到TON!**\n\n哈希: `{hash}`\n\n🔗 验证: {url}\n\n证明已永久保存! 🔒",
        "withdraw_success": "✅ **提款已发送!**\n\n{amount} TON已发送到您的钱包。\n交易将在~30秒后显示。",
        "withdraw_min": "⚠️ 最低提款: 0.05 TON\n\n您的余额: {balance} TON",
        "withdraw_no_wallet": "⚠️ 请先发送您的TON钱包地址。\n\n例如: `EQB...` 或 `UQA...`",
        "lang_changed": "✅ 语言已更改为中文",
        "referral_stats": "🎁 **推荐计划**\n\n**您的链接:**\n`{url}`\n\n**佣金:** 5%\n**推荐人数:** {count}\n**收益:** {earnings} TON\n**已提取:** {withdrawn} TON\n**可用:** {available} TON\n\n💡 使用 /withdraw 提现!",
        "status_active": "✅ **订阅有效**\n\n到期: {expiry}\n\n无限封存已启用!",
        "status_inactive": "❌ **无有效订阅**\n\n余额: {credits} TON\n\n使用 /subscribe 获取无限!",
        "photo_prompt": "📸 **不错的截图!**\n\n1星即可永久封存到TON。",
        "file_prompt": "📄 **文件已收到!**\n\n1星即可永久封存到TON。",
        "sealing_progress": "⏳ **正在封存到区块链...**\n\n您的文件正在TON上获取时间戳。\n这需要5-15秒。",
        "network_busy": "⚠️ **TON网络繁忙**\n\n我们正在自动重试。请稍候。",
        "retry_prompt": "🔄 **重试**\n\n点击下方按钮重试。",
        "lottery_tickets": "🎫 彩票: {count}张",
        "pot_grew": "💰 奖池增加 +{amount} TON",
        "good_luck": "🍀 祝周日好运!",
    }
}


def get_text(user_id: int, key: str, **kwargs) -> str:
    """Get translated text for user"""
    lang = user_languages.get(user_id, "en")
    text = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, TRANSLATIONS["en"].get(key, key))
    if kwargs:
        text = text.format(**kwargs)
    return text

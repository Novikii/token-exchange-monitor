#!/usr/bin/env python3
"""
Token Exchange Monitor - Multi-Chain Edition
监控以太坊和BSC上的代币转账，支持交易所充值和巨鲸转账两种模式
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple

import yaml
import requests

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========== 配置加载模块 ==========

def load_config() -> dict:
    """加载config.yaml配置文件"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config.yaml not found!")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config.yaml: {e}")
        raise


def load_state() -> dict:
    """加载last_state.json，记录已处理的交易"""
    if os.path.exists('last_state.json'):
        try:
            with open('last_state.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("last_state.json corrupted, resetting...")
            return {'processed_tx': []}
    return {'processed_tx': []}


def save_state(state: dict):
    """保存状态到last_state.json"""
    with open('last_state.json', 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_exchange_addresses() -> dict:
    """加载已知交易所地址库"""
    if os.path.exists('exchange_addresses.json'):
        try:
            with open('exchange_addresses.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning("exchange_addresses.json corrupted, resetting...")
            return {}
    return {}


def save_exchange_addresses(addresses: dict):
    """保存交易所地址库"""
    with open('exchange_addresses.json', 'w', encoding='utf-8') as f:
        json.dump(addresses, f, indent=2, ensure_ascii=False)


# ========== API调用模块 ==========

def get_token_transfers(
    contract_address: str,
    api_key: str,
    api_url: str,
    page: int = 1,
    offset: int = 100
) -> List[dict]:
    """
    获取代币转账记录
    使用Etherscan API: module=logs&action=getLogs
    监控Transfer事件: Transfer(address,address,uint256)
    """
    # 获取最新区块号
    try:
        block_response = requests.get(
            api_url,
            params={
                'module': 'proxy',
                'action': 'eth_blockNumber',
                'apikey': api_key
            },
            timeout=10
        )
        latest_block = int(block_response.json()['result'], 16)
        from_block = latest_block - 500  # 查询最近500个区块（约2小时）
    except Exception as e:
        logger.error(f"Failed to get block number: {e}")
        from_block = 0

    # Transfer事件的topic0
    # Transfer(address indexed from, address indexed to, uint256 value)
    transfer_topic = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'

    params = {
        'module': 'logs',
        'action': 'getLogs',
        'address': contract_address,
        'fromBlock': from_block,
        'toBlock': 'latest',
        'topic0': transfer_topic,
        'apikey': api_key
    }

    try:
        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data['status'] == '1' and data['message'] == 'OK':
            # 转换logs格式为类似tokentx的格式
            transfers = []
            for log in data['result']:
                # 解析log数据
                # topics[1] = from address (padded to 32 bytes)
                # topics[2] = to address (padded to 32 bytes)
                # data = value (hex)
                if len(log['topics']) >= 3:
                    from_addr = '0x' + log['topics'][1][-40:]  # 取最后40个字符
                    to_addr = '0x' + log['topics'][2][-40:]
                    value = log['data']  # hex value

                    transfers.append({
                        'hash': log['transactionHash'],
                        'from': from_addr,
                        'to': to_addr,
                        'value': str(int(value, 16)),  # 转为十进制字符串
                        'timeStamp': str(int(log['timeStamp'], 16))
                    })

            # 按时间倒序排序，返回最近的N条
            transfers.sort(key=lambda x: int(x['timeStamp']), reverse=True)
            return transfers[:offset]

        elif data['status'] == '0' and 'No records found' in data.get('message', ''):
            return []
        else:
            logger.error(f"API error: {data.get('message', 'Unknown error')}")
            logger.debug(f"API response: {data}")
            return []

    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return []


def get_token_price(coingecko_id: str, api_url: str) -> Optional[float]:
    """
    获取代币USD价格
    使用CoinGecko API
    """
    url = f"{api_url}/simple/price"
    params = {
        'ids': coingecko_id,
        'vs_currencies': 'usd'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if coingecko_id in data and 'usd' in data[coingecko_id]:
            return float(data[coingecko_id]['usd'])
        else:
            logger.error(f"Price not found for {coingecko_id}")
            return None

    except requests.RequestException as e:
        logger.error(f"CoinGecko API failed: {e}")
        return None


def get_address_label_from_web(address: str, explorer_url: str) -> Optional[str]:
    """
    从区块链浏览器网页抓取地址标签
    注意：此方法有速率限制，仅作为备用方案
    """
    # 简化实现：暂时返回None，依赖缓存库
    # 完整实现需要HTML解析，这里不展开
    return None


# ========== 地址标签识别模块 ==========

def check_is_exchange_deposit(
    to_address: str,
    to_label: Optional[str],
    from_label: Optional[str],
    exchanges: List[str],
    deposit_keywords: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    检查是否为外部地址向交易所充值

    返回：(是否匹配, 交易所名称)

    规则：
    1. To地址标签必须包含交易所名称
    2. To地址标签必须包含Deposit关键字
    3. From地址标签不能包含任何交易所名称（排除内部转账）
    """
    if not to_label:
        return False, None

    # 转换为小写进行匹配
    to_label_lower = to_label.lower()

    # 检查To地址是否包含Deposit关键字
    has_deposit_keyword = any(
        keyword.lower() in to_label_lower
        for keyword in deposit_keywords
    )

    if not has_deposit_keyword:
        return False, None

    # 检查To地址是否包含交易所名称
    matched_exchange = None
    for exchange in exchanges:
        if exchange.lower() in to_label_lower:
            matched_exchange = exchange
            break

    if not matched_exchange:
        return False, None

    # 检查From地址是否包含交易所名称（排除内部转账）
    if from_label:
        from_label_lower = from_label.lower()
        for exchange in exchanges:
            if exchange.lower() in from_label_lower:
                logger.debug(f"Skipping internal transfer: {from_label} -> {to_label}")
                return False, None

    return True, matched_exchange


# ========== Lark消息推送模块 ==========

def format_message(tx_info: dict) -> str:
    """
    格式化Lark消息 - 根据监控模式使用不同模板
    """
    if tx_info['notification_type'] == 'exchange_deposit':
        # 模式1: 交易所充值提醒
        from_display = tx_info['from_address_short']
        if tx_info.get('from_label'):
            from_display += f" ({tx_info['from_label']})"

        return f"""🚨 代币转入交易所提醒

💎 代币: {tx_info['token_symbol']} ({tx_info['token_name']}) [{tx_info['chain_name']}]
💰 金额: {tx_info['amount']:,.2f} {tx_info['token_symbol']}
💵 价值: ≈ ${tx_info['usd_value']:,.2f} USD
📤 发送方: {from_display}
🏦 接收方: {tx_info['to_label']}
🔗 {tx_info['chain_name']}Scan: {tx_info['explorer_url']}/tx/{tx_info['tx_hash']}
⏰ 时间: {tx_info['timestamp']}

---
监控系统 | Powered by GitHub Actions"""

    elif tx_info['notification_type'] == 'whale_transfer':
        # 模式2: 巨鲸转账提醒
        from_display = tx_info['from_address_short']
        if tx_info.get('from_label'):
            from_display += f" ({tx_info['from_label']})"

        to_display = tx_info['to_address_short']
        if tx_info.get('to_label'):
            to_display += f" ({tx_info['to_label']})"

        return f"""🐋 大额转账提醒

💎 代币: {tx_info['token_symbol']} ({tx_info['token_name']}) [{tx_info['chain_name']}]
💰 金额: {tx_info['amount']:,.2f} {tx_info['token_symbol']}
💵 价值: ≈ ${tx_info['usd_value']:,.2f} USD
📤 发送方: {from_display}
📥 接收方: {to_display}
🔗 {tx_info['chain_name']}Scan: {tx_info['explorer_url']}/tx/{tx_info['tx_hash']}
⏰ 时间: {tx_info['timestamp']}

⚠️ 巨鲸模式：所有>${tx_info['usd_value']:,.0f}转账都会播报
---
监控系统 | Powered by GitHub Actions"""

    return ""


def send_lark_notification(webhook_url: str, tx_info: dict):
    """发送Lark消息"""
    message = {
        "msg_type": "text",
        "content": {
            "text": format_message(tx_info)
        }
    }

    try:
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()

        result = response.json()
        if result.get('code') != 0:
            raise Exception(f"Lark webhook failed: {result.get('msg')}")

    except requests.RequestException as e:
        logger.error(f"Failed to send Lark notification: {e}")
        raise


# ========== 主流程 ==========

def main():
    """主监控流程 - 支持多链和双监控模式"""
    logger.info("="*60)
    logger.info("Token Exchange Monitor - Starting")
    logger.info("="*60)

    # 1. 加载配置和状态
    config = load_config()
    state = load_state()
    exchange_addresses = load_exchange_addresses()

    # 2. 获取环境变量
    lark_webhook_url = os.getenv('LARK_WEBHOOK_URL')
    if not lark_webhook_url:
        logger.error("LARK_WEBHOOK_URL not set!")
        return

    total_notifications = 0

    # 3. 遍历每条链
    for chain in config['chains']:
        logger.info("")
        logger.info("="*60)
        logger.info(f"Checking chain: {chain['name']}")
        logger.info("="*60)

        # 获取该链的API Key
        api_key = os.getenv(chain['api_key_env'])
        if not api_key:
            logger.error(f"❌ API Key not found: {chain['api_key_env']}")
            continue

        # 遍历该链上的每个代币
        for token in chain['tokens']:
            logger.info("")
            logger.info(f"📊 Checking {token['symbol']} on {chain['name']}...")

            # 3.1 获取代币价格
            price = get_token_price(
                token['coingecko_id'],
                config['coingecko_api_url']
            )

            if not price:
                logger.warning(f"⚠️  Failed to get price for {token['symbol']}, skipping...")
                continue

            logger.info(f"💵 Current price: ${price:.6f}")

            # 3.2 获取最近的转账记录
            transfers = get_token_transfers(
                contract_address=token['contract'],
                api_key=api_key,
                api_url=chain['explorer_api'],
                offset=100  # 获取最近100笔交易
            )

            if not transfers:
                logger.info(f"ℹ️  No transactions found")
                continue

            logger.info(f"📝 Found {len(transfers)} transactions")

            # 3.3 过滤和处理交易
            notified_count = 0

            for tx in transfers:
                # 构造唯一标识
                tx_key = f"{chain['name']}:{token['symbol']}:{tx['hash']}"

                # 跳过已处理的交易
                if tx_key in state.get('processed_tx', []):
                    continue

                # 计算金额（考虑decimals）
                try:
                    amount = int(tx['value']) / (10 ** token['decimals'])
                except (ValueError, KeyError):
                    logger.warning(f"Invalid transaction value: {tx.get('hash')}")
                    continue

                usd_value = amount * price

                # 检查是否超过阈值
                if usd_value < config['usd_threshold']:
                    continue

                # 根据监控模式决定是否播报
                should_notify = False
                notification_type = None
                to_label = None
                from_label = None

                if token['monitor_mode'] == 'exchange_deposit':
                    # 模式1: 仅播报交易所充值
                    to_label = exchange_addresses.get(tx['to'].lower())
                    from_label = exchange_addresses.get(tx['from'].lower())

                    # 检查是否匹配交易所充值
                    is_deposit, exchange_name = check_is_exchange_deposit(
                        tx['to'], to_label, from_label,
                        config['exchanges'], config['deposit_keywords']
                    )

                    if is_deposit:
                        should_notify = True
                        notification_type = 'exchange_deposit'

                elif token['monitor_mode'] == 'whale_transfer':
                    # 模式2: 所有大额转账都播报
                    should_notify = True
                    notification_type = 'whale_transfer'
                    to_label = exchange_addresses.get(tx['to'].lower())
                    from_label = exchange_addresses.get(tx['from'].lower())

                if not should_notify:
                    continue

                # 构造交易信息
                tx_info = {
                    'notification_type': notification_type,
                    'chain_name': chain['name'],
                    'explorer_url': chain['explorer_url'],
                    'token_symbol': token['symbol'],
                    'token_name': token['name'],
                    'amount': amount,
                    'usd_value': usd_value,
                    'from_address': tx['from'],
                    'from_address_short': f"{tx['from'][:6]}...{tx['from'][-4:]}",
                    'from_label': from_label,
                    'to_address': tx['to'],
                    'to_address_short': f"{tx['to'][:6]}...{tx['to'][-4:]}",
                    'to_label': to_label,
                    'tx_hash': tx['hash'],
                    'timestamp': datetime.fromtimestamp(
                        int(tx['timeStamp'])
                    ).strftime('%Y-%m-%d %H:%M:%S UTC')
                }

                # 发送Lark通知
                try:
                    send_lark_notification(lark_webhook_url, tx_info)
                    logger.info(f"✅ Notified: {tx['hash'][:10]}... (${usd_value:,.2f})")
                    notified_count += 1
                    total_notifications += 1
                except Exception as e:
                    logger.error(f"❌ Failed to send notification: {e}")

                # 记录已处理
                if 'processed_tx' not in state:
                    state['processed_tx'] = []
                state['processed_tx'].append(tx_key)

                # 避免发送过快
                time.sleep(1)

            logger.info(f"✅ {token['symbol']}: {notified_count} notifications sent")

    # 4. 限制状态文件大小，只保留最近1000条
    if 'processed_tx' in state:
        state['processed_tx'] = state['processed_tx'][-1000:]

    # 5. 保存状态
    save_state(state)
    save_exchange_addresses(exchange_addresses)

    logger.info("")
    logger.info("="*60)
    logger.info(f"✅ Monitor cycle completed - Total notifications: {total_notifications}")
    logger.info("="*60)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)

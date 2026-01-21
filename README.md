# Token Exchange Monitor (Multi-Chain)

代币交易所监控系统 - 支持多链和双监控模式

## 功能特性

### 🔗 多链支持
- **Ethereum主网**: 监控ZRO等代币
- **BSC链**: 监控River等代币
- **易扩展**: 支持添加Polygon、Arbitrum等50+条EVM链

### 🎯 双监控模式

#### 1. 交易所充值模式 (`exchange_deposit`)
- 精准识别外部地址向交易所Deposit地址的转账
- 自动排除交易所内部转账（资金归集等）
- 适用于已上主流交易所的代币

#### 2. 巨鲸转账模式 (`whale_transfer`)
- 监控所有大额转账，不限接收方
- 适用于未上主流交易所的早期项目
- 帮助发现巨鲸动向

### 💰 智能过滤
- 统一USD阈值：$5,000
- 实时价格获取（CoinGecko）
- 避免重复播报

### 📢 飞书通知
- 实时推送到飞书群
- 包含完整交易信息：金额、USD价值、发送方、接收方、交易链接
- 不同模式使用不同消息模板

## 快速开始

### 1. Fork/Clone本仓库

```bash
git clone https://github.com/YOUR_USERNAME/token-exchange-monitor.git
cd token-exchange-monitor
```

### 2. 配置GitHub Secrets

进入仓库设置：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

添加以下2个Secrets：

| Name | Value | 说明 |
|------|-------|------|
| `ETHERSCAN_API_KEY` | `464NNH3W2W27BTG5Z4EKX453UT7UWYHZA2` | Etherscan API V2密钥（支持50+链） |
| `LARK_WEBHOOK_URL` | `https://open.larksuite.com/...` | 飞书机器人Webhook地址 |

### 3. 修改配置文件（可选）

编辑 `config.yaml` 来：
- 添加新代币
- 调整USD阈值
- 添加新交易所
- 更改监控模式

### 4. 启用GitHub Actions

首次推送后，workflow会自动启动。你也可以手动触发：

1. 进入 `Actions` 标签页
2. 选择 `Token Exchange Monitor (Multi-Chain)`
3. 点击 `Run workflow`

### 5. 查看运行日志

- 进入 `Actions` 标签页
- 点击最近的运行记录
- 查看详细日志

## 配置说明

### config.yaml结构

```yaml
# 全局USD阈值
usd_threshold: 5000

# 链配置
chains:
  - name: Ethereum
    explorer_api: "https://api.etherscan.io/api"
    explorer_url: "https://etherscan.io"
    api_key_env: "ETHERSCAN_API_KEY"
    tokens:
      - name: LayerZero
        symbol: ZRO
        contract: "0x6985884C4392D348587B19cb9eAAf157F13271cd"
        coingecko_id: "layerzero"
        decimals: 18
        monitor_mode: "exchange_deposit"  # 或 "whale_transfer"
```

### 监控模式选择

| 监控模式 | 适用场景 | 过滤规则 |
|---------|---------|---------|
| `exchange_deposit` | 已上主流交易所 | To=交易所Deposit<br>From≠交易所<br>金额>$5000 |
| `whale_transfer` | 未上主流交易所/早期项目 | 金额>$5000 |

## 添加新代币

### 1. 以太坊链代币

在 `config.yaml` 的 `Ethereum` 链下添加：

```yaml
- name: Uniswap
  symbol: UNI
  contract: "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
  coingecko_id: "uniswap"
  decimals: 18
  monitor_mode: "exchange_deposit"
```

### 2. BSC链代币

在 `config.yaml` 的 `BSC` 链下添加：

```yaml
- name: PancakeSwap
  symbol: CAKE
  contract: "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82"
  coingecko_id: "pancakeswap-token"
  decimals: 18
  monitor_mode: "whale_transfer"
```

### 3. 获取代币信息

- **Contract地址**: 从区块链浏览器复制
- **CoinGecko ID**: 访问 https://www.coingecko.com 搜索代币，URL中的ID
- **Decimals**: 通常是18，可从区块链浏览器查看

## 添加新链

Etherscan API V2支持50+条EVM链，添加新链只需在 `config.yaml` 添加配置：

```yaml
- name: Polygon
  chain_id: 137
  explorer_api: "https://api.polygonscan.com/api"
  explorer_url: "https://polygonscan.com"
  api_key_env: "ETHERSCAN_API_KEY"  # 使用同一个API Key
  tokens:
    - name: Aave
      symbol: AAVE
      contract: "0xD6DF932A45C0f255f85145f286eA0b292B21C90B"
      coingecko_id: "aave"
      decimals: 18
      monitor_mode: "exchange_deposit"
```

支持的链包括：Ethereum, BSC, Polygon, Arbitrum, Optimism, Avalanche等。

## 调整监控频率

编辑 `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    - cron: '*/5 * * * *'   # 每5分钟
    # - cron: '*/10 * * * *'  # 每10分钟（推荐）
    # - cron: '*/30 * * * *'  # 每30分钟
```

## 本地测试

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export ETHERSCAN_API_KEY="464NNH3W2W27BTG5Z4EKX453UT7UWYHZA2"
export LARK_WEBHOOK_URL="https://open.larksuite.com/..."

# 运行监控脚本
python monitor.py
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `monitor.py` | 主监控脚本 |
| `config.yaml` | 配置文件 |
| `.github/workflows/monitor.yml` | GitHub Actions工作流 |
| `requirements.txt` | Python依赖 |
| `last_state.json` | 状态文件（自动生成，记录已处理交易） |
| `exchange_addresses.json` | 交易所地址库（自动生成） |

## 常见问题

### Q: 如何获取Etherscan API Key？
A: 访问 https://etherscan.io/register 注册账号，然后在 https://etherscan.io/myapikey 获取免费API Key。

### Q: Etherscan API V2是什么？
A: 新版API支持用一个密钥访问50+条EVM链，包括Ethereum、BSC、Polygon等，无需单独申请。

### Q: 如何获取飞书Webhook地址？
A: 在飞书群中添加机器人，选择"自定义机器人"，复制Webhook地址。

### Q: 为什么没有收到通知？
A:
1. 检查GitHub Actions是否正常运行（`Actions` 标签页）
2. 确认Secrets配置正确
3. 查看运行日志，确认是否有符合条件的交易
4. 首次运行只会监控最近的交易，不追溯历史

### Q: 如何避免重复播报？
A: 系统自动记录已处理的交易hash到 `last_state.json`，避免重复播报。

### Q: GitHub Actions免费额度够用吗？
A: 免费版每月2000分钟。每10分钟运行一次，每次约1-2分钟，月消耗约8640分钟。建议设置为10分钟/次。

### Q: 如何添加更多交易所？
A: 编辑 `config.yaml` 的 `exchanges` 列表，添加交易所名称关键字即可。

## 技术架构

- **语言**: Python 3.11+
- **定时任务**: GitHub Actions
- **API**: Etherscan API V2 + CoinGecko API
- **通知**: 飞书Webhook
- **状态存储**: Git commit（自动持久化）

## 贡献

欢迎提交Issue和Pull Request！

## License

MIT License

## 支持

如有问题，请在GitHub Issues中提问。

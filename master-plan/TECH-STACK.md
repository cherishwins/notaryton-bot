# Technical Architecture & Implementation

## Overview

This document details the technical stack, architecture, and implementation steps for the MemeSeal Labs ecosystem.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEMESEAL LABS ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │   TELEGRAM      │
                              │   USERS         │
                              └────────┬────────┘
                                       │
                                       ▼
                    ┌─────────────────────────────────────┐
                    │         TELEGRAM MINI APPS          │
                    │  (Next.js + React + TailwindCSS)    │
                    ├─────────┬─────────┬─────────┬───────┤
                    │MemeSeal │MemeScan │MemeMarket│MemeMart│
                    └────┬────┴────┬────┴────┬────┴───┬───┘
                         │         │         │        │
                         └─────────┴────┬────┴────────┘
                                        │
                                        ▼
                         ┌──────────────────────────┐
                         │      API GATEWAY         │
                         │   (Node.js / FastAPI)    │
                         └────────────┬─────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           │                          │                          │
           ▼                          ▼                          ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   CORE SERVICES     │   │   DATA SERVICES     │   │  EXTERNAL SERVICES  │
├─────────────────────┤   ├─────────────────────┤   ├─────────────────────┤
│ • Auth Service      │   │ • PostgreSQL        │   │ • TON Blockchain    │
│ • Order Service     │   │ • Redis (cache)     │   │ • RedStone Oracle   │
│ • Payment Service   │   │ • Indexer           │   │ • The Odds API      │
│ • Notification Svc  │   │ • Analytics         │   │ • Stripe            │
│ • Oracle Service    │   │                     │   │ • ShipStation       │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
           │                          │                          │
           └──────────────────────────┼──────────────────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │     TON BLOCKCHAIN       │
                         ├──────────────────────────┤
                         │ • MemeMarket Contracts   │
                         │ • MemeSeal Contracts     │
                         │ • Payment Processing     │
                         └──────────────────────────┘
```

---

## Frontend Stack

### Shared Components

All Mini Apps share:
- **Framework**: Next.js 14+ (App Router)
- **UI**: React 18+ with TypeScript
- **Styling**: TailwindCSS + shadcn/ui components
- **State**: Zustand (lightweight) or TanStack Query
- **Wallet**: TON Connect 2.0

### Project Structure

```
memeseal-labs/
├── apps/
│   ├── memeseal/          # Timestamping app (existing)
│   ├── memescan/          # Token terminal (existing)
│   ├── mememarket/        # Prediction exchange (NEW)
│   └── mememart/          # Hardware store (NEW)
├── packages/
│   ├── ui/                # Shared UI components
│   ├── config/            # Shared configs (tailwind, tsconfig)
│   ├── contracts/         # TON contract interfaces
│   └── api-client/        # Shared API client
├── services/
│   ├── api/               # Backend API
│   ├── indexer/           # Blockchain indexer
│   └── oracle/            # Oracle service
└── contracts/
    ├── market/            # MemeMarket contracts (Tact)
    └── seal/              # MemeSeal contracts (existing)
```

### Mini App Configuration

```typescript
// apps/mememarket/src/app/layout.tsx

import { TonConnectUIProvider } from '@tonconnect/ui-react';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <script src="https://telegram.org/js/telegram-web-app.js" />
      </head>
      <body>
        <TonConnectUIProvider
          manifestUrl="https://mememarket.app/tonconnect-manifest.json"
        >
          {children}
        </TonConnectUIProvider>
      </body>
    </html>
  );
}
```

### TON Connect Integration

```typescript
// packages/contracts/src/ton-connect.ts

import { TonConnect } from '@tonconnect/sdk';
import { useTonConnectUI } from '@tonconnect/ui-react';

export const useWallet = () => {
  const [tonConnectUI] = useTonConnectUI();

  const connect = async () => {
    await tonConnectUI.openModal();
  };

  const sendTransaction = async (params: {
    to: string;
    amount: string;
    payload?: string;
  }) => {
    const transaction = {
      validUntil: Math.floor(Date.now() / 1000) + 600, // 10 min
      messages: [
        {
          address: params.to,
          amount: params.amount,
          payload: params.payload,
        },
      ],
    };

    const result = await tonConnectUI.sendTransaction(transaction);
    return result;
  };

  return {
    connect,
    sendTransaction,
    connected: tonConnectUI.connected,
    address: tonConnectUI.account?.address,
  };
};
```

---

## Backend Stack

### API Service

**Framework**: Node.js with Fastify (or Python FastAPI)

```typescript
// services/api/src/index.ts

import Fastify from 'fastify';
import cors from '@fastify/cors';
import { marketsRoutes } from './routes/markets';
import { ordersRoutes } from './routes/orders';
import { productsRoutes } from './routes/products';
import { webhooksRoutes } from './routes/webhooks';

const fastify = Fastify({ logger: true });

// Plugins
fastify.register(cors, { origin: true });

// Routes
fastify.register(marketsRoutes, { prefix: '/api/markets' });
fastify.register(ordersRoutes, { prefix: '/api/orders' });
fastify.register(productsRoutes, { prefix: '/api/products' });
fastify.register(webhooksRoutes, { prefix: '/api/webhooks' });

// Start
fastify.listen({ port: 3000, host: '0.0.0.0' });
```

### Database Schema

```sql
-- PostgreSQL Schema

-- Markets (MemeMarket)
CREATE TABLE markets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_address VARCHAR(66) NOT NULL UNIQUE,
  question TEXT NOT NULL,
  description TEXT,
  category VARCHAR(50),
  resolution_time TIMESTAMP NOT NULL,
  oracle_type VARCHAR(20), -- 'redstone', 'sports_api', 'manual'
  oracle_config JSONB,
  status VARCHAR(20) DEFAULT 'active', -- active, resolved, disputed
  outcome BOOLEAN,
  yes_price DECIMAL(5,4) DEFAULT 0.5000,
  no_price DECIMAL(5,4) DEFAULT 0.5000,
  total_volume DECIMAL(20,6) DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  resolved_at TIMESTAMP
);

CREATE INDEX idx_markets_status ON markets(status);
CREATE INDEX idx_markets_category ON markets(category);
CREATE INDEX idx_markets_resolution ON markets(resolution_time);

-- Positions
CREATE TABLE positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  market_id UUID REFERENCES markets(id),
  user_address VARCHAR(66) NOT NULL,
  side BOOLEAN NOT NULL, -- true = YES, false = NO
  amount DECIMAL(20,6) NOT NULL,
  entry_price DECIMAL(5,4) NOT NULL,
  status VARCHAR(20) DEFAULT 'open', -- open, closed, claimed
  created_at TIMESTAMP DEFAULT NOW(),
  closed_at TIMESTAMP
);

CREATE INDEX idx_positions_user ON positions(user_address);
CREATE INDEX idx_positions_market ON positions(market_id);

-- Orders (MemeMarket)
CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  market_id UUID REFERENCES markets(id),
  user_address VARCHAR(66) NOT NULL,
  side BOOLEAN NOT NULL,
  order_type VARCHAR(10), -- 'limit', 'market'
  price DECIMAL(5,4),
  amount DECIMAL(20,6) NOT NULL,
  filled_amount DECIMAL(20,6) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'pending', -- pending, filled, cancelled
  tx_hash VARCHAR(66),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Products (MemeMart)
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  category VARCHAR(50),
  price_usd DECIMAL(10,2) NOT NULL,
  price_ton DECIMAL(20,6),
  stock_qty INTEGER DEFAULT 0,
  image_urls TEXT[],
  specifications JSONB,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW()
);

-- E-commerce Orders
CREATE TABLE ecommerce_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number VARCHAR(20) UNIQUE NOT NULL,
  user_address VARCHAR(66),
  user_telegram_id BIGINT,
  status VARCHAR(20) DEFAULT 'pending',
  subtotal_usd DECIMAL(10,2),
  shipping_usd DECIMAL(10,2),
  total_usd DECIMAL(10,2),
  total_ton DECIMAL(20,6),
  payment_method VARCHAR(20), -- 'ton', 'usdt', 'stripe'
  payment_tx_hash VARCHAR(66),
  shipping_address JSONB,
  tracking_number VARCHAR(100),
  seal_tx_hash VARCHAR(66), -- MemeSeal certificate
  created_at TIMESTAMP DEFAULT NOW(),
  paid_at TIMESTAMP,
  shipped_at TIMESTAMP
);

-- Order Items
CREATE TABLE order_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id UUID REFERENCES ecommerce_orders(id),
  product_id UUID REFERENCES products(id),
  quantity INTEGER NOT NULL,
  unit_price_usd DECIMAL(10,2) NOT NULL
);
```

### Indexer Service

Watches blockchain for events and syncs to database:

```typescript
// services/indexer/src/index.ts

import { TonClient } from '@ton/ton';
import { Address, Cell } from '@ton/core';

class MarketIndexer {
  private client: TonClient;
  private lastProcessedLt: bigint = 0n;

  constructor() {
    this.client = new TonClient({
      endpoint: 'https://mainnet.tonhubapi.com/jsonRPC',
    });
  }

  async watchMarketContract(address: string) {
    const contractAddress = Address.parse(address);

    setInterval(async () => {
      const txs = await this.client.getTransactions(contractAddress, {
        limit: 100,
        lt: this.lastProcessedLt.toString(),
      });

      for (const tx of txs) {
        await this.processTransaction(tx);
        this.lastProcessedLt = BigInt(tx.lt);
      }
    }, 5000); // Poll every 5 seconds
  }

  async processTransaction(tx: any) {
    // Parse transaction, extract events
    // Update database with new orders, positions, etc.
  }
}
```

---

## Smart Contract Architecture

### MemeMarket Contracts (Tact)

```
contracts/market/
├── market-factory.tact    # Creates new markets
├── market.tact            # Individual market logic
├── order-book.tact        # Order matching
├── oracle-adapter.tact    # Oracle integration
└── tests/
    ├── market.spec.ts
    └── factory.spec.ts
```

#### Market Factory Contract

```tact
// contracts/market/market-factory.tact

import "@stdlib/deploy";
import "@stdlib/ownable";

message CreateMarket {
    question: String;
    resolutionTime: Int as uint64;
    oracleAddress: Address;
    oracleConfig: Cell;
}

message MarketCreated {
    marketAddress: Address;
    creator: Address;
    question: String;
}

contract MarketFactory with Deployable, Ownable {
    owner: Address;
    marketCount: Int as uint64;
    creationFee: Int as coins;

    init(owner: Address) {
        self.owner = owner;
        self.marketCount = 0;
        self.creationFee = ton("1"); // 1 TON to create market
    }

    receive(msg: CreateMarket) {
        require(context().value >= self.creationFee, "Insufficient fee");
        require(msg.resolutionTime > now(), "Resolution must be future");

        // Deploy new market contract
        let marketInit = initOf Market(
            self.marketCount,
            msg.question,
            msg.resolutionTime,
            msg.oracleAddress,
            msg.oracleConfig,
            sender()
        );

        send(SendParameters{
            to: contractAddress(marketInit),
            value: ton("0.1"), // Initial balance
            mode: SendIgnoreErrors,
            code: marketInit.code,
            data: marketInit.data,
            body: "init".asComment()
        });

        self.marketCount += 1;

        // Emit event
        emit(MarketCreated{
            marketAddress: contractAddress(marketInit),
            creator: sender(),
            question: msg.question
        }.toCell());
    }

    get fun getMarketCount(): Int {
        return self.marketCount;
    }

    get fun getCreationFee(): Int {
        return self.creationFee;
    }
}
```

#### Individual Market Contract

```tact
// contracts/market/market.tact

import "@stdlib/deploy";

struct Order {
    trader: Address;
    side: Bool;        // true = YES, false = NO
    amount: Int;
    price: Int;        // 0-100 (percentage)
    timestamp: Int;
}

struct Position {
    yesAmount: Int;
    noAmount: Int;
    averagePrice: Int;
}

message PlaceOrder {
    side: Bool;
    price: Int;
}

message CancelOrder {
    orderId: Int;
}

message ResolveMarket {
    outcome: Bool;
    proof: Cell;
}

message ClaimWinnings {
    // No params needed, uses sender address
}

contract Market {
    marketId: Int;
    question: String;
    resolutionTime: Int;
    oracleAddress: Address;
    oracleConfig: Cell;
    creator: Address;

    resolved: Bool;
    outcome: Bool;

    // Order book
    nextOrderId: Int;
    yesOrders: map<Int, Order>;
    noOrders: map<Int, Order>;

    // Positions
    positions: map<Address, Position>;

    // Stats
    totalYesAmount: Int;
    totalNoAmount: Int;
    totalVolume: Int;

    init(
        marketId: Int,
        question: String,
        resolutionTime: Int,
        oracleAddress: Address,
        oracleConfig: Cell,
        creator: Address
    ) {
        self.marketId = marketId;
        self.question = question;
        self.resolutionTime = resolutionTime;
        self.oracleAddress = oracleAddress;
        self.oracleConfig = oracleConfig;
        self.creator = creator;

        self.resolved = false;
        self.outcome = false;
        self.nextOrderId = 0;
        self.totalYesAmount = 0;
        self.totalNoAmount = 0;
        self.totalVolume = 0;
    }

    receive(msg: PlaceOrder) {
        require(!self.resolved, "Market resolved");
        require(now() < self.resolutionTime, "Market closed");
        require(msg.price > 0 && msg.price < 100, "Invalid price");

        let amount = context().value;
        require(amount >= ton("0.1"), "Min order 0.1 TON");

        // Create order
        let order = Order{
            trader: sender(),
            side: msg.side,
            amount: amount,
            price: msg.price,
            timestamp: now()
        };

        // Try to match with existing orders
        self.matchOrder(order);
    }

    receive(msg: ResolveMarket) {
        require(sender() == self.oracleAddress, "Only oracle");
        require(now() >= self.resolutionTime, "Too early");
        require(!self.resolved, "Already resolved");

        // Verify oracle proof
        self.verifyOracleProof(msg.proof);

        self.resolved = true;
        self.outcome = msg.outcome;
    }

    receive(msg: ClaimWinnings) {
        require(self.resolved, "Not resolved");

        let position = self.positions.get(sender());
        require(position != null, "No position");

        let payout = self.calculatePayout(position!!, self.outcome);
        require(payout > 0, "Nothing to claim");

        // 2% fee on winnings
        let fee = payout * 2 / 100;
        let netPayout = payout - fee;

        // Send payout
        send(SendParameters{
            to: sender(),
            value: netPayout,
            mode: SendIgnoreErrors,
            body: "Winnings".asComment()
        });

        // Clear position
        self.positions.set(sender(), null);
    }

    fun matchOrder(order: Order) {
        // Matching logic
        let oppositeOrders = order.side ? self.noOrders : self.yesOrders;
        let targetPrice = 100 - order.price; // Complementary price

        // Find matching orders at or below target price
        // ... implementation
    }

    fun calculatePayout(position: Position, outcome: Bool): Int {
        if (outcome) {
            return position.yesAmount * 100 / position.averagePrice;
        } else {
            return position.noAmount * 100 / (100 - position.averagePrice);
        }
    }

    fun verifyOracleProof(proof: Cell) {
        // Verify RedStone signature or other oracle proof
    }

    // Getters
    get fun getMarketInfo(): Cell {
        // Return market state
    }

    get fun getOrderBook(): Cell {
        // Return current orders
    }

    get fun getPosition(addr: Address): Position? {
        return self.positions.get(addr);
    }
}
```

### Contract Deployment

```typescript
// scripts/deploy-market-factory.ts

import { toNano, Address } from '@ton/ton';
import { MarketFactory } from '../wrappers/MarketFactory';
import { compile, NetworkProvider } from '@ton/blueprint';

export async function run(provider: NetworkProvider) {
  const marketFactory = provider.open(
    MarketFactory.createFromConfig(
      {
        owner: provider.sender().address!,
      },
      await compile('MarketFactory')
    )
  );

  await marketFactory.sendDeploy(provider.sender(), toNano('0.5'));

  await provider.waitForDeploy(marketFactory.address);

  console.log('MarketFactory deployed at:', marketFactory.address);
}
```

---

## Oracle Service

### RedStone Integration (Crypto Prices)

```typescript
// services/oracle/src/redstone.ts

import { WrapperBuilder } from '@redstone-finance/evm-connector';
import { TonClient } from '@ton/ton';

class RedStoneOracle {
  async getPriceData(symbol: string): Promise<{
    price: number;
    timestamp: number;
    signature: string;
  }> {
    // Fetch from RedStone
    const response = await fetch(
      `https://api.redstone.finance/prices?symbol=${symbol}&provider=redstone`
    );
    const data = await response.json();

    return {
      price: data.value,
      timestamp: data.timestamp,
      signature: data.signature,
    };
  }

  async resolveMarket(marketAddress: string, symbol: string, targetPrice: number) {
    const priceData = await this.getPriceData(symbol);

    // Determine outcome
    const outcome = priceData.price >= targetPrice;

    // Build resolution message with proof
    const proof = this.buildProof(priceData);

    // Send to contract
    await this.sendResolution(marketAddress, outcome, proof);
  }
}
```

### Sports Oracle (The Odds API)

```typescript
// services/oracle/src/sports.ts

const ODDS_API_KEY = process.env.ODDS_API_KEY;
const ODDS_API_BASE = 'https://api.the-odds-api.com/v4';

interface GameResult {
  id: string;
  sport: string;
  homeTeam: string;
  awayTeam: string;
  homeScore: number;
  awayScore: number;
  completed: boolean;
}

class SportsOracle {
  async getGameResult(gameId: string): Promise<GameResult> {
    const response = await fetch(
      `${ODDS_API_BASE}/sports/upcoming/scores?apiKey=${ODDS_API_KEY}&eventIds=${gameId}`
    );
    const data = await response.json();
    return data[0];
  }

  async resolveMarket(
    marketAddress: string,
    gameId: string,
    marketType: 'winner' | 'spread' | 'total',
    params: any
  ) {
    const result = await this.getGameResult(gameId);

    if (!result.completed) {
      throw new Error('Game not completed');
    }

    let outcome: boolean;

    switch (marketType) {
      case 'winner':
        outcome = result.homeScore > result.awayScore
          ? params.pick === 'home'
          : params.pick === 'away';
        break;

      case 'spread':
        const margin = result.homeScore - result.awayScore;
        outcome = margin > params.spread;
        break;

      case 'total':
        const total = result.homeScore + result.awayScore;
        outcome = total > params.line;
        break;
    }

    // Sign result
    const signature = await this.signResult(result, outcome);

    // Send to contract
    await this.sendResolution(marketAddress, outcome, signature);
  }

  private async signResult(result: GameResult, outcome: boolean): Promise<string> {
    // Sign with oracle private key
    // This proves we attested to the result
  }
}
```

---

## Payment Processing

### TON Payments (MemeMarket)

Handled directly by smart contracts - users send TON to contract addresses.

### TON Wallet Pay (MemeMart)

```typescript
// services/api/src/payments/wallet-pay.ts

import { WalletPay } from '@wallet-pay/sdk';

const walletPay = new WalletPay({
  apiKey: process.env.WALLET_PAY_API_KEY,
  testMode: process.env.NODE_ENV !== 'production',
});

export async function createPayment(order: EcommerceOrder) {
  const payment = await walletPay.createOrder({
    amount: {
      currencyCode: 'TON',
      amount: order.totalTon.toString(),
    },
    description: `MemeMart Order #${order.orderNumber}`,
    externalId: order.id,
    timeoutSeconds: 1800, // 30 min
    customerTelegramUserId: order.userTelegramId,
    returnUrl: `https://mememart.app/orders/${order.id}`,
    failReturnUrl: 'https://mememart.app/checkout',
  });

  return {
    paymentId: payment.id,
    payUrl: payment.payLink,
  };
}

// Webhook handler
export async function handlePaymentWebhook(payload: any, signature: string) {
  // Verify signature
  const isValid = walletPay.verifyWebhookSignature(payload, signature);
  if (!isValid) throw new Error('Invalid signature');

  if (payload.status === 'PAID') {
    const orderId = payload.externalId;

    // Update order
    await db.ecommerceOrders.update({
      where: { id: orderId },
      data: {
        status: 'paid',
        paidAt: new Date(),
        paymentTxHash: payload.paymentTransactionHash,
      },
    });

    // Trigger fulfillment
    await fulfillOrder(orderId);
  }
}
```

### Stripe Fallback (MemeMart)

```typescript
// services/api/src/payments/stripe.ts

import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

export async function createStripeCheckout(order: EcommerceOrder) {
  const session = await stripe.checkout.sessions.create({
    payment_method_types: ['card'],
    line_items: order.items.map(item => ({
      price_data: {
        currency: 'usd',
        product_data: {
          name: item.product.name,
          images: item.product.imageUrls,
        },
        unit_amount: Math.round(item.unitPriceUsd * 100),
      },
      quantity: item.quantity,
    })),
    mode: 'payment',
    success_url: `https://mememart.app/orders/${order.id}?success=true`,
    cancel_url: 'https://mememart.app/checkout',
    metadata: {
      orderId: order.id,
    },
  });

  return session.url;
}
```

---

## Deployment

### Infrastructure (Render)

```yaml
# render.yaml

services:
  # API Service
  - type: web
    name: memeseal-api
    env: node
    repo: https://github.com/yourusername/memeseal-labs
    buildCommand: cd services/api && npm install && npm run build
    startCommand: cd services/api && npm start
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: memeseal-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: memeseal-redis
          type: redis
          property: connectionString

  # Indexer Service
  - type: worker
    name: memeseal-indexer
    env: node
    repo: https://github.com/yourusername/memeseal-labs
    buildCommand: cd services/indexer && npm install && npm run build
    startCommand: cd services/indexer && npm start

  # Oracle Service
  - type: worker
    name: memeseal-oracle
    env: node
    repo: https://github.com/yourusername/memeseal-labs
    buildCommand: cd services/oracle && npm install && npm run build
    startCommand: cd services/oracle && npm start

databases:
  - name: memeseal-db
    plan: starter
    postgresMajorVersion: 16

# Redis for caching
  - type: redis
    name: memeseal-redis
    plan: starter
```

### Mini Apps (Vercel)

```json
// apps/mememarket/vercel.json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "env": {
    "NEXT_PUBLIC_API_URL": "@api_url",
    "NEXT_PUBLIC_TON_NETWORK": "mainnet"
  }
}
```

---

## Testing Strategy

### Smart Contract Tests

```typescript
// contracts/market/tests/market.spec.ts

import { Blockchain, SandboxContract } from '@ton/sandbox';
import { Market } from '../wrappers/Market';
import { toNano } from '@ton/core';

describe('Market', () => {
  let blockchain: Blockchain;
  let market: SandboxContract<Market>;

  beforeEach(async () => {
    blockchain = await Blockchain.create();

    market = blockchain.openContract(
      Market.createFromConfig({
        question: 'Test market?',
        resolutionTime: Math.floor(Date.now() / 1000) + 86400,
        oracleAddress: blockchain.treasury('oracle').address,
      })
    );

    await market.sendDeploy(blockchain.treasury('deployer').getSender(), toNano('0.5'));
  });

  it('should place order', async () => {
    const trader = await blockchain.treasury('trader');

    const result = await market.sendPlaceOrder(
      trader.getSender(),
      toNano('1'),
      { side: true, price: 60 }
    );

    expect(result.transactions).toHaveTransaction({
      success: true,
    });
  });

  it('should match orders', async () => {
    const buyer = await blockchain.treasury('buyer');
    const seller = await blockchain.treasury('seller');

    // YES order at 60
    await market.sendPlaceOrder(
      buyer.getSender(),
      toNano('1'),
      { side: true, price: 60 }
    );

    // NO order at 40 (complementary)
    await market.sendPlaceOrder(
      seller.getSender(),
      toNano('0.67'),
      { side: false, price: 40 }
    );

    // Check positions created
    const buyerPosition = await market.getPosition(buyer.address);
    expect(buyerPosition.yesAmount).toBeGreaterThan(0);
  });

  it('should resolve and claim', async () => {
    // ... setup positions

    const oracle = await blockchain.treasury('oracle');

    // Fast forward time
    blockchain.now = Math.floor(Date.now() / 1000) + 86401;

    // Resolve
    await market.sendResolve(
      oracle.getSender(),
      { outcome: true, proof: Cell.EMPTY }
    );

    // Claim
    const result = await market.sendClaim(buyer.getSender());

    expect(result.transactions).toHaveTransaction({
      success: true,
      // Check payout sent
    });
  });
});
```

### API Tests

```typescript
// services/api/tests/markets.spec.ts

import { describe, it, expect } from 'vitest';
import { app } from '../src/app';

describe('Markets API', () => {
  it('should list markets', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/api/markets',
    });

    expect(response.statusCode).toBe(200);
    const data = response.json();
    expect(Array.isArray(data.markets)).toBe(true);
  });

  it('should get market by id', async () => {
    const response = await app.inject({
      method: 'GET',
      url: '/api/markets/123',
    });

    expect(response.statusCode).toBe(200);
  });
});
```

---

## Monitoring & Observability

### Logging

```typescript
// services/api/src/logger.ts

import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    target: 'pino-pretty',
    options: { colorize: true },
  },
});

// Usage
logger.info({ orderId, amount }, 'Order created');
logger.error({ err, marketId }, 'Failed to resolve market');
```

### Metrics

```typescript
// Prometheus metrics
import { Registry, Counter, Histogram } from 'prom-client';

const registry = new Registry();

export const ordersCreated = new Counter({
  name: 'mememarket_orders_created_total',
  help: 'Total orders created',
  labelNames: ['market', 'side'],
  registers: [registry],
});

export const orderLatency = new Histogram({
  name: 'mememarket_order_latency_seconds',
  help: 'Order processing latency',
  registers: [registry],
});
```

### Alerting

- **Uptime monitoring**: Render built-in
- **Error tracking**: Sentry
- **Blockchain monitoring**: Custom alerts for contract events

---

## Security Checklist

### Smart Contracts
- [ ] Professional audit (CertiK, Trail of Bits, etc.)
- [ ] Internal review
- [ ] Bug bounty program
- [ ] Gradual rollout with limits
- [ ] Emergency pause mechanism

### API
- [ ] Rate limiting
- [ ] Input validation
- [ ] SQL injection prevention (parameterized queries)
- [ ] CORS configuration
- [ ] Webhook signature verification

### Infrastructure
- [ ] HTTPS everywhere
- [ ] Environment variables for secrets
- [ ] Regular dependency updates
- [ ] Backup strategy

---

## Next Steps

1. **Read**: [ROADMAP.md](./ROADMAP.md) for implementation timeline
2. **Start coding**: Set up monorepo structure
3. **Deploy testnet contracts**: Test with fake TON
4. **Build MVP frontend**: Basic market UI

---

## Resources

### TON Development
- [TON Docs](https://docs.ton.org)
- [Tact Language](https://tact-lang.org)
- [TON Blueprint](https://github.com/ton-org/blueprint)
- [TON Connect](https://docs.ton.org/develop/dapps/ton-connect)

### Reference Implementations
- [STON.fi Contracts](https://github.com/ston-fi/dex-core)
- [Tact Examples](https://github.com/tact-lang/tact/tree/main/examples)

### APIs
- [RedStone Oracles](https://docs.redstone.finance)
- [The Odds API](https://the-odds-api.com/liveapi/guides/v4/)
- [TON Wallet Pay](https://docs.wallet.tg)

import { Blockchain, SandboxContract, TreasuryContract } from '@ton/sandbox';
import { toNano, Address } from '@ton/core';
import { SealBetFactory } from '../build/SealBetFactory/SealBetFactory_SealBetFactory';
import { Market } from '../build/SealBetFactory/SealBetFactory_Market';
import '@ton/test-utils';

describe('SealBetFactory', () => {
    let blockchain: Blockchain;
    let deployer: SandboxContract<TreasuryContract>;
    let feeCollector: SandboxContract<TreasuryContract>;
    let sealBetFactory: SandboxContract<SealBetFactory>;

    beforeEach(async () => {
        blockchain = await Blockchain.create();

        deployer = await blockchain.treasury('deployer');
        feeCollector = await blockchain.treasury('feeCollector');

        sealBetFactory = blockchain.openContract(
            await SealBetFactory.fromInit(deployer.address, feeCollector.address)
        );

        const deployResult = await sealBetFactory.send(
            deployer.getSender(),
            {
                value: toNano('0.05'),
            },
            { $$type: 'Deploy', queryId: 0n },
        );

        expect(deployResult.transactions).toHaveTransaction({
            from: deployer.address,
            to: sealBetFactory.address,
            deploy: true,
            success: true,
        });
    });

    it('should deploy', async () => {
        // Verify initial state
        const owner = await sealBetFactory.getGetOwner();
        expect(owner.toString()).toBe(deployer.address.toString());

        const collector = await sealBetFactory.getGetFeeCollector();
        expect(collector.toString()).toBe(feeCollector.address.toString());

        const marketCount = await sealBetFactory.getGetMarketCount();
        expect(marketCount).toBe(0n);
    });

    it('should create a market', async () => {
        const deadline = BigInt(Math.floor(Date.now() / 1000) + 86400); // 1 day from now

        const createResult = await sealBetFactory.send(
            deployer.getSender(),
            {
                value: toNano('0.1'),
            },
            {
                $$type: 'CreateMarket',
                question: 'Will BTC hit $150k by March 2025?',
                deadline: deadline,
            },
        );

        expect(createResult.transactions).toHaveTransaction({
            from: deployer.address,
            to: sealBetFactory.address,
            success: true,
        });

        // Check market count increased
        const marketCount = await sealBetFactory.getGetMarketCount();
        expect(marketCount).toBe(1n);

        // Get market address
        const marketAddress = await sealBetFactory.getGetMarket(1n);
        expect(marketAddress).not.toBeNull();
    });

    it('should reject market creation from non-owner', async () => {
        const nonOwner = await blockchain.treasury('nonOwner');
        const deadline = BigInt(Math.floor(Date.now() / 1000) + 86400);

        const createResult = await sealBetFactory.send(
            nonOwner.getSender(),
            {
                value: toNano('0.1'),
            },
            {
                $$type: 'CreateMarket',
                question: 'Test market',
                deadline: deadline,
            },
        );

        expect(createResult.transactions).toHaveTransaction({
            from: nonOwner.address,
            to: sealBetFactory.address,
            success: false,
        });
    });
});

describe('Market', () => {
    let blockchain: Blockchain;
    let deployer: SandboxContract<TreasuryContract>;
    let feeCollector: SandboxContract<TreasuryContract>;
    let sealBetFactory: SandboxContract<SealBetFactory>;
    let market: SandboxContract<Market>;
    let bettor1: SandboxContract<TreasuryContract>;
    let bettor2: SandboxContract<TreasuryContract>;

    const deadline = BigInt(Math.floor(Date.now() / 1000) + 86400); // 1 day from now

    beforeEach(async () => {
        blockchain = await Blockchain.create();

        deployer = await blockchain.treasury('deployer');
        feeCollector = await blockchain.treasury('feeCollector');
        bettor1 = await blockchain.treasury('bettor1');
        bettor2 = await blockchain.treasury('bettor2');

        // Deploy factory
        sealBetFactory = blockchain.openContract(
            await SealBetFactory.fromInit(deployer.address, feeCollector.address)
        );

        await sealBetFactory.send(
            deployer.getSender(),
            { value: toNano('0.05') },
            { $$type: 'Deploy', queryId: 0n },
        );

        // Create a market
        await sealBetFactory.send(
            deployer.getSender(),
            { value: toNano('0.1') },
            {
                $$type: 'CreateMarket',
                question: 'Will BTC hit $150k by March 2025?',
                deadline: deadline,
            },
        );

        // Get market contract
        const marketAddress = await sealBetFactory.getGetMarket(1n);
        market = blockchain.openContract(Market.fromAddress(marketAddress!));
    });

    it('should accept YES bets', async () => {
        const betResult = await market.send(
            bettor1.getSender(),
            { value: toNano('1.05') }, // 1 TON bet + 0.05 gas
            {
                $$type: 'Bet',
                outcome: 1n, // YES
            },
        );

        expect(betResult.transactions).toHaveTransaction({
            from: bettor1.address,
            to: market.address,
            success: true,
        });

        const yesPool = await market.getGetYesPool();
        expect(yesPool).toBe(toNano('1'));
    });

    it('should accept NO bets', async () => {
        const betResult = await market.send(
            bettor1.getSender(),
            { value: toNano('2.05') }, // 2 TON bet + 0.05 gas
            {
                $$type: 'Bet',
                outcome: 0n, // NO
            },
        );

        expect(betResult.transactions).toHaveTransaction({
            from: bettor1.address,
            to: market.address,
            success: true,
        });

        const noPool = await market.getGetNoPool();
        expect(noPool).toBe(toNano('2'));
    });

    it('should calculate odds correctly', async () => {
        // Bettor1 bets 1 TON on YES
        await market.send(
            bettor1.getSender(),
            { value: toNano('1.05') },
            { $$type: 'Bet', outcome: 1n },
        );

        // Bettor2 bets 3 TON on NO
        await market.send(
            bettor2.getSender(),
            { value: toNano('3.05') },
            { $$type: 'Bet', outcome: 0n },
        );

        const odds = await market.getGetOdds();
        // YES pool = 1, NO pool = 3, Total = 4
        // YES odds = 1/4 = 2500 basis points (25%)
        // NO odds = 3/4 = 7500 basis points (75%)
        expect(odds.get(1n)).toBe(2500n);
        expect(odds.get(0n)).toBe(7500n);
    });

    it('should resolve market and allow claims', async () => {
        // Place bets
        await market.send(
            bettor1.getSender(),
            { value: toNano('1.05') },
            { $$type: 'Bet', outcome: 1n }, // YES
        );

        await market.send(
            bettor2.getSender(),
            { value: toNano('1.05') },
            { $$type: 'Bet', outcome: 0n }, // NO
        );

        // Fast forward past deadline
        blockchain.now = Number(deadline) + 1;

        // Resolve market (YES wins) - deployer is the admin/owner
        const resolveResult = await market.send(
            deployer.getSender(),
            { value: toNano('0.05') },
            {
                $$type: 'Resolve',
                winningOutcome: 1n, // YES
            },
        );

        expect(resolveResult.transactions).toHaveTransaction({
            from: deployer.address,
            to: market.address,
            success: true,
        });

        const isResolved = await market.getIsResolved();
        expect(isResolved).toBe(true);

        // Bettor1 (YES winner) claims
        const balanceBefore = await bettor1.getBalance();

        const claimResult = await market.send(
            bettor1.getSender(),
            { value: toNano('0.05') },
            { $$type: 'Claim' },
        );

        expect(claimResult.transactions).toHaveTransaction({
            from: bettor1.address,
            to: market.address,
            success: true,
        });

        // Check bettor1 received payout
        // They should get: 1 TON (their bet) + 1 TON (loser's pool) - 2% fee
        // = 2 TON - 0.04 TON = 1.96 TON (minus gas)
        const balanceAfter = await bettor1.getBalance();
        expect(balanceAfter).toBeGreaterThan(balanceBefore);
    });

    it('should reject bets after deadline', async () => {
        // Fast forward past deadline
        blockchain.now = Number(deadline) + 1;

        const betResult = await market.send(
            bettor1.getSender(),
            { value: toNano('1.05') },
            { $$type: 'Bet', outcome: 1n },
        );

        expect(betResult.transactions).toHaveTransaction({
            from: bettor1.address,
            to: market.address,
            success: false,
        });
    });

    it('should reject claims before resolution', async () => {
        // Place a bet
        await market.send(
            bettor1.getSender(),
            { value: toNano('1.05') },
            { $$type: 'Bet', outcome: 1n },
        );

        // Try to claim without resolution
        const claimResult = await market.send(
            bettor1.getSender(),
            { value: toNano('0.05') },
            { $$type: 'Claim' },
        );

        expect(claimResult.transactions).toHaveTransaction({
            from: bettor1.address,
            to: market.address,
            success: false,
        });
    });

    it('should track user bets correctly', async () => {
        // Place multiple bets
        await market.send(
            bettor1.getSender(),
            { value: toNano('1.05') },
            { $$type: 'Bet', outcome: 1n },
        );

        await market.send(
            bettor1.getSender(),
            { value: toNano('2.05') },
            { $$type: 'Bet', outcome: 1n },
        );

        const userBet = await market.getGetUserBet(bettor1.address, 1n);
        expect(userBet).toBe(toNano('3')); // 1 + 2 = 3 TON
    });
});

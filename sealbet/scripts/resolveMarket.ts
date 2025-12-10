import { toNano, Address } from '@ton/core';
import { Market } from '../build/SealBetFactory/SealBetFactory_Market';
import { NetworkProvider } from '@ton/blueprint';

export async function run(provider: NetworkProvider, args: string[]) {
    const marketAddress = args[0];
    const outcome = args[1]; // '0' for NO, '1' for YES

    if (!marketAddress || !outcome) {
        console.log('Usage: npx blueprint run resolveMarket <market_address> <outcome>');
        console.log('Example: npx blueprint run resolveMarket EQ... 1');
        console.log('  outcome: 0 = NO, 1 = YES');
        return;
    }

    const winningOutcome = BigInt(parseInt(outcome));
    if (winningOutcome !== 0n && winningOutcome !== 1n) {
        console.log('Invalid outcome. Must be 0 (NO) or 1 (YES)');
        return;
    }

    const market = provider.open(
        Market.fromAddress(Address.parse(marketAddress))
    );

    // Check market state
    const question = await market.getGetQuestion();
    const deadline = await market.getGetDeadline();
    const isResolved = await market.getIsResolved();
    const yesPool = await market.getGetYesPool();
    const noPool = await market.getGetNoPool();

    console.log('Market:', question);
    console.log('Deadline:', new Date(Number(deadline) * 1000).toISOString());
    console.log('Already resolved:', isResolved);
    console.log('YES Pool:', (Number(yesPool) / 1e9).toFixed(2), 'TON');
    console.log('NO Pool:', (Number(noPool) / 1e9).toFixed(2), 'TON');

    if (isResolved) {
        console.log('Market is already resolved!');
        return;
    }

    const now = Math.floor(Date.now() / 1000);
    if (now < Number(deadline)) {
        console.log('Market deadline has not passed yet!');
        console.log('Current time:', new Date(now * 1000).toISOString());
        return;
    }

    console.log('\nResolving market with outcome:', winningOutcome === 1n ? 'YES' : 'NO');

    await market.send(
        provider.sender(),
        {
            value: toNano('0.05'),
        },
        {
            $$type: 'Resolve',
            winningOutcome: winningOutcome,
        },
    );

    console.log('Resolution transaction sent!');

    // Wait and verify
    await new Promise(resolve => setTimeout(resolve, 5000));

    const newIsResolved = await market.getIsResolved();
    const resolvedOutcome = await market.getGetWinningOutcome();

    console.log('Market resolved:', newIsResolved);
    console.log('Winning outcome:', resolvedOutcome === 1n ? 'YES' : 'NO');
}

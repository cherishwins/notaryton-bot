import { toNano, Address } from '@ton/core';
import { SealBetFactory } from '../build/SealBetFactory/SealBetFactory_SealBetFactory';
import { NetworkProvider } from '@ton/blueprint';

export async function run(provider: NetworkProvider, args: string[]) {
    // Factory address should be provided as argument or hardcoded after deployment
    const factoryAddress = args[0];

    if (!factoryAddress) {
        console.log('Usage: npx blueprint run createMarket <factory_address>');
        console.log('Example: npx blueprint run createMarket EQ...');
        return;
    }

    const sealBetFactory = provider.open(
        SealBetFactory.fromAddress(Address.parse(factoryAddress))
    );

    // Example market: BTC above $150k by March 31, 2025
    const question = 'Will BTC hit $150,000 by March 31, 2025?';
    const deadline = BigInt(Math.floor(new Date('2025-03-31T23:59:59Z').getTime() / 1000));

    console.log('Creating market...');
    console.log('Question:', question);
    console.log('Deadline:', new Date(Number(deadline) * 1000).toISOString());

    await sealBetFactory.send(
        provider.sender(),
        {
            value: toNano('0.1'),
        },
        {
            $$type: 'CreateMarket',
            question: question,
            deadline: deadline,
        },
    );

    console.log('Market creation transaction sent!');

    // Wait a bit and check market count
    await new Promise(resolve => setTimeout(resolve, 5000));

    const marketCount = await sealBetFactory.getGetMarketCount();
    console.log('Total markets:', marketCount.toString());

    if (marketCount > 0n) {
        const marketAddress = await sealBetFactory.getGetMarket(marketCount);
        console.log('New market address:', marketAddress?.toString());
    }
}

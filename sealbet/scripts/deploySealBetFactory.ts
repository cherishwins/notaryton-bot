import { toNano, Address } from '@ton/core';
import { SealBetFactory } from '../build/SealBetFactory/SealBetFactory_SealBetFactory';
import { NetworkProvider } from '@ton/blueprint';

export async function run(provider: NetworkProvider) {
    // Get deployer address (will be both owner and fee collector for now)
    const sender = provider.sender();
    const deployerAddress = sender.address;

    if (!deployerAddress) {
        throw new Error('Deployer address not available');
    }

    console.log('Deploying SealBetFactory...');
    console.log('Owner:', deployerAddress.toString());
    console.log('Fee Collector:', deployerAddress.toString());

    const sealBetFactory = provider.open(
        await SealBetFactory.fromInit(deployerAddress, deployerAddress)
    );

    await sealBetFactory.send(
        sender,
        {
            value: toNano('0.05'),
        },
        { $$type: 'Deploy', queryId: 0n },
    );

    await provider.waitForDeploy(sealBetFactory.address);

    console.log('SealBetFactory deployed at:', sealBetFactory.address.toString());

    // Verify deployment
    const owner = await sealBetFactory.getGetOwner();
    console.log('Verified owner:', owner.toString());

    const marketCount = await sealBetFactory.getGetMarketCount();
    console.log('Initial market count:', marketCount.toString());
}

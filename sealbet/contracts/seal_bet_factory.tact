import "@stdlib/deploy";
import "./market";

// Message to create a new market
message CreateMarket {
    question: String;
    deadline: Int as uint64;
}

// Event emitted when market is created
message MarketCreated {
    marketAddress: Address;
    question: String;
    deadline: Int as uint64;
}

// Factory contract - creates and tracks prediction markets
contract SealBetFactory with Deployable {
    // Owner/admin address
    owner: Address;

    // Fee collector address (receives 2% of winnings)
    feeCollector: Address;

    // Counter for market IDs
    marketCount: Int as uint32 = 0;

    // Track all markets: id -> address
    markets: map<Int, Address>;

    init(owner: Address, feeCollector: Address) {
        self.owner = owner;
        self.feeCollector = feeCollector;
    }

    // Create a new prediction market
    receive(msg: CreateMarket) {
        // Only owner can create markets (for MVP)
        require(sender() == self.owner, "Only owner can create markets");
        require(msg.deadline > now(), "Deadline must be in future");

        // Increment market count
        self.marketCount = self.marketCount + 1;

        // Calculate market contract init
        let marketInit: StateInit = initOf Market(
            msg.question,
            msg.deadline,
            self.owner,  // Owner is admin of market (can resolve)
            self.feeCollector
        );

        // Deploy the market contract
        let marketAddress: Address = contractAddress(marketInit);

        send(SendParameters{
            to: marketAddress,
            value: ton("0.05"),
            mode: SendIgnoreErrors,
            code: marketInit.code,
            data: marketInit.data,
            body: Deploy{queryId: 0}.toCell()
        });

        // Store market address
        self.markets.set(self.marketCount, marketAddress);

        // Emit event
        emit(MarketCreated{
            marketAddress: marketAddress,
            question: msg.question,
            deadline: msg.deadline
        }.toCell());

        // Return remaining gas
        cashback(sender());
    }

    // Resolve a market (forwarded to market contract)
    receive(msg: Resolve) {
        require(sender() == self.owner, "Only owner can resolve");
        // Forward to all markets or specific market based on context
        // For MVP, we'll resolve directly on market contract
    }

    // Transfer ownership
    receive("transfer_ownership") {
        require(sender() == self.owner, "Only owner");
        // Implementation: accept new owner address in message
    }

    // Getters
    get fun getOwner(): Address {
        return self.owner;
    }

    get fun getFeeCollector(): Address {
        return self.feeCollector;
    }

    get fun getMarketCount(): Int {
        return self.marketCount;
    }

    get fun getMarket(id: Int): Address? {
        return self.markets.get(id);
    }

    get fun getMarketAddress(question: String, deadline: Int): Address {
        let marketInit: StateInit = initOf Market(
            question,
            deadline,
            self.owner,
            self.feeCollector
        );
        return contractAddress(marketInit);
    }
}

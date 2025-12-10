import "@stdlib/deploy";

// Bet message - user places a bet
message Bet {
    outcome: Int as uint8;  // 0 = NO, 1 = YES
}

// Resolve message - admin resolves the market
message Resolve {
    winningOutcome: Int as uint8;  // 0 = NO, 1 = YES
}

// Claim message - user claims their winnings
message Claim {}

// Market contract - Parimutuel betting market
contract Market with Deployable {
    // Market metadata
    question: String;
    deadline: Int as uint64;

    // Admin (factory address)
    admin: Address;

    // Pool balances
    yesPool: Int as coins = 0;
    noPool: Int as coins = 0;

    // User bets tracking: address -> (outcome, amount)
    // Using maps for YES and NO separately
    yesBets: map<Address, Int as coins>;
    noBets: map<Address, Int as coins>;

    // Resolution state
    resolved: Bool = false;
    winningOutcome: Int as uint8 = 0;

    // Fee (2% = 200 basis points)
    fee: Int as uint16 = 200;
    feeCollector: Address;

    // Total fees collected
    feesCollected: Int as coins = 0;

    init(question: String, deadline: Int, owner: Address, feeCollector: Address) {
        self.question = question;
        self.deadline = deadline;
        self.admin = owner;  // Owner is the admin who can resolve
        self.feeCollector = feeCollector;
    }

    // Place a bet
    receive(msg: Bet) {
        // Check market is still open
        require(now() < self.deadline, "Market closed");
        require(!self.resolved, "Market already resolved");
        require(msg.outcome == 0 || msg.outcome == 1, "Invalid outcome");

        // Get bet amount (message value minus gas reserve)
        let betAmount: Int = context().value - ton("0.05");
        require(betAmount > 0, "Bet amount too small");

        let sender: Address = sender();

        if (msg.outcome == 1) {
            // YES bet
            self.yesPool = self.yesPool + betAmount;
            let existing: Int? = self.yesBets.get(sender);
            if (existing != null) {
                self.yesBets.set(sender, existing!! + betAmount);
            } else {
                self.yesBets.set(sender, betAmount);
            }
        } else {
            // NO bet
            self.noPool = self.noPool + betAmount;
            let existing: Int? = self.noBets.get(sender);
            if (existing != null) {
                self.noBets.set(sender, existing!! + betAmount);
            } else {
                self.noBets.set(sender, betAmount);
            }
        }
    }

    // Admin resolves the market
    receive(msg: Resolve) {
        require(sender() == self.admin, "Only admin can resolve");
        require(now() >= self.deadline, "Market not yet closed");
        require(!self.resolved, "Already resolved");
        require(msg.winningOutcome == 0 || msg.winningOutcome == 1, "Invalid outcome");

        self.resolved = true;
        self.winningOutcome = msg.winningOutcome;
    }

    // User claims their winnings
    receive(msg: Claim) {
        require(self.resolved, "Market not resolved");

        let sender: Address = sender();
        let payout: Int = 0;

        if (self.winningOutcome == 1) {
            // YES won - pay YES bettors
            let userBet: Int? = self.yesBets.get(sender);
            require(userBet != null, "No winning bet found");
            require(userBet!! > 0, "Already claimed");

            // Calculate payout: user_bet + (user_bet / yes_pool) * no_pool
            // Minus 2% fee
            let winnerShare: Int = userBet!! * self.noPool / self.yesPool;
            let grossPayout: Int = userBet!! + winnerShare;
            let feeAmount: Int = grossPayout * self.fee / 10000;
            payout = grossPayout - feeAmount;

            self.feesCollected = self.feesCollected + feeAmount;
            self.yesBets.set(sender, 0);  // Mark as claimed
        } else {
            // NO won - pay NO bettors
            let userBet: Int? = self.noBets.get(sender);
            require(userBet != null, "No winning bet found");
            require(userBet!! > 0, "Already claimed");

            // Calculate payout: user_bet + (user_bet / no_pool) * yes_pool
            // Minus 2% fee
            let winnerShare: Int = userBet!! * self.yesPool / self.noPool;
            let grossPayout: Int = userBet!! + winnerShare;
            let feeAmount: Int = grossPayout * self.fee / 10000;
            payout = grossPayout - feeAmount;

            self.feesCollected = self.feesCollected + feeAmount;
            self.noBets.set(sender, 0);  // Mark as claimed
        }

        // Send payout
        require(payout > 0, "Nothing to claim");
        send(SendParameters{
            to: sender,
            value: payout,
            mode: SendIgnoreErrors,
            body: "SealBet Payout".asComment()
        });
    }

    // Admin withdraws collected fees
    receive("withdraw_fees") {
        require(sender() == self.admin, "Only admin");
        require(self.feesCollected > 0, "No fees to withdraw");

        let amount: Int = self.feesCollected;
        self.feesCollected = 0;

        send(SendParameters{
            to: self.feeCollector,
            value: amount,
            mode: SendIgnoreErrors,
            body: "SealBet Fees".asComment()
        });
    }

    // Getters
    get fun getQuestion(): String {
        return self.question;
    }

    get fun getDeadline(): Int {
        return self.deadline;
    }

    get fun getPools(): map<Int, Int> {
        let pools: map<Int, Int> = emptyMap();
        pools.set(0, self.noPool);
        pools.set(1, self.yesPool);
        return pools;
    }

    get fun getYesPool(): Int {
        return self.yesPool;
    }

    get fun getNoPool(): Int {
        return self.noPool;
    }

    get fun isResolved(): Bool {
        return self.resolved;
    }

    get fun getWinningOutcome(): Int {
        return self.winningOutcome;
    }

    get fun getUserBet(user: Address, outcome: Int): Int {
        if (outcome == 1) {
            let bet: Int? = self.yesBets.get(user);
            return bet != null ? bet!! : 0;
        } else {
            let bet: Int? = self.noBets.get(user);
            return bet != null ? bet!! : 0;
        }
    }

    get fun getOdds(): map<Int, Int> {
        // Returns implied probability in basis points (0-10000)
        let total: Int = self.yesPool + self.noPool;
        let odds: map<Int, Int> = emptyMap();

        if (total > 0) {
            odds.set(0, self.noPool * 10000 / total);
            odds.set(1, self.yesPool * 10000 / total);
        } else {
            odds.set(0, 5000);
            odds.set(1, 5000);
        }
        return odds;
    }

    get fun getFeesCollected(): Int {
        return self.feesCollected;
    }
}

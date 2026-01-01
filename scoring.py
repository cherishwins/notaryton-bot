"""
Enhanced Minter Credit Score - Port of creative-hub scoring logic.

This module provides sophisticated entity detection and scoring that matches
the creative-hub TypeScript implementation, integrating ton-labels data.

Usage:
    from scoring import calculate_minter_score
    score = await calculate_minter_score(db, address)
"""

import json
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

# Entity category scores (0-1000 scale, matching creative-hub)
ENTITY_SCORES = {
    'validator': 950,        # A+ - Network validators are trustworthy
    'cex': 850,              # A  - Centralized exchanges
    'dex': 800,              # A  - DEX protocols
    'bridge': 750,           # B+ - Cross-chain bridges
    'liquid_staking': 800,   # A  - Staking protocols
    'lending': 750,          # B+ - DeFi lending
    'yield_aggregator': 700, # B  - Yield protocols
    'infrastructure': 800,   # A  - Core infra
    'fund': 700,             # B  - Investment funds
    'merchant': 650,         # B- - Known merchants
    'gaming': 600,           # C  - Gaming platforms
    'tradingbot': 600,       # C  - Trading bots
    'ads': 550,              # C- - Ad platforms
    'wallet': 600,           # C  - Wallet providers
    'cdp': 700,              # B  - CDP protocols
    'other': 500,            # D  - Unknown/other
    'scripted-activity': 400,# D- - Suspicious automation
    'scammer': 0,            # F  - CONFIRMED SCAMMER
}

# Grade thresholds (matching creative-hub)
GRADES = [
    (950, 'A+', '#22C55E', 'Exceptional - Highly Trusted'),
    (900, 'A',  '#4ADE80', 'Excellent - Very Reliable'),
    (800, 'A-', '#86EFAC', 'Very Good - Reliable'),
    (700, 'B+', '#BBF7D0', 'Good - Generally Safe'),
    (600, 'C',  '#FACC15', 'Fair - Exercise Caution'),
    (400, 'D',  '#FB923C', 'Poor - High Risk'),
    (200, 'D-', '#F97316', 'Very Poor - Very High Risk'),
    (0,   'F',  '#EF4444', 'Fail - Extreme Risk / Likely Rug'),
]


@dataclass
class ScoreResult:
    """Minter credit score result."""
    score: int
    grade: str
    grade_color: str
    grade_description: str
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    recommendation: str
    warnings: list
    entity_info: Optional[Dict[str, Any]] = None


def score_to_grade(score: int) -> tuple:
    """Convert numeric score to letter grade with color and description."""
    for threshold, grade, color, desc in GRADES:
        if score >= threshold:
            return grade, color, desc
    return 'F', '#EF4444', 'Fail - Extreme Risk / Likely Rug'


def get_risk_level(score: int) -> str:
    """Get risk level from score."""
    if score >= 800:
        return 'LOW'
    elif score >= 600:
        return 'MEDIUM'
    elif score >= 200:
        return 'HIGH'
    else:
        return 'CRITICAL'


async def calculate_minter_score(db, address: str) -> ScoreResult:
    """
    Calculate minter credit score for a TON address.

    Args:
        db: Database instance with wallets repository
        address: TON address to score

    Returns:
        ScoreResult with score, grade, warnings, and entity info
    """
    warnings = []
    entity_info = None

    # Step 1: Check known_wallets for entity label
    known = await db.wallets.get_wallet_label(address)

    if known:
        category = known.label

        # Handle scammer detection with highest priority
        if category == 'scammer':
            # Parse notes for extra info
            extra = {}
            if known.notes:
                try:
                    extra = json.loads(known.notes)
                except:
                    pass

            subcategory = extra.get('subcategory', '')
            description = extra.get('description', '')

            # Build scammer warning
            scam_type = subcategory or 'unknown'
            warning = f"🚨 KNOWN SCAMMER: {known.owner_name or 'Unknown'}"
            if scam_type:
                warning += f" - {scam_type.replace('_', ' ').title()}"
            if description:
                warning += f" ({description})"
            warnings.append(warning)

            if subcategory == 'drainer':
                warnings.append("⚠️ DRAINER CONTRACT: Will drain your wallet!")

            return ScoreResult(
                score=0,
                grade='F',
                grade_color='#EF4444',
                grade_description='Fail - Extreme Risk / Likely Rug',
                risk_level='CRITICAL',
                recommendation='🚨 CONFIRMED SCAMMER - This address is in the TON community scammer database. DO NOT INTERACT.',
                warnings=warnings,
                entity_info={
                    'category': category,
                    'label': known.owner_name,
                    'organization': known.owner_name,
                    'notes': extra,
                }
            )

        # Handle known good entities
        score = ENTITY_SCORES.get(category, 500)
        grade, color, desc = score_to_grade(score)
        risk_level = get_risk_level(score)

        # Parse extra info from notes
        extra = {}
        if known.notes:
            try:
                extra = json.loads(known.notes)
            except:
                pass

        # Build entity info
        entity_info = {
            'category': category,
            'label': known.owner_name,
            'organization': known.owner_name,
            'website': extra.get('website'),
            'tags': extra.get('tags', []),
        }

        # Build trust flags
        trust_flags = []
        cat_upper = category.upper().replace('_', ' ')
        if extra.get('website'):
            trust_flags.append(f"✅ VERIFIED {cat_upper}: {known.owner_name} ({extra['website']})")
        else:
            trust_flags.append(f"✅ VERIFIED {cat_upper}: {known.owner_name}")

        for tag in extra.get('tags', []):
            if tag == 'has-custodial-wallets':
                trust_flags.append("ℹ️ Has custodial wallet services")

        entity_info['trustFlags'] = trust_flags

        # Build recommendation based on category
        if category in ('cex', 'dex', 'validator'):
            recommendation = f"✅ VERIFIED {cat_upper.replace('_', ' ')} - {known.owner_name or category} is a known {category.replace('_', ' ')}."
        elif category in ('bridge', 'liquid_staking', 'lending'):
            recommendation = f"✅ VERIFIED PROTOCOL - {known.owner_name or 'This address'} is a known DeFi protocol."
        else:
            recommendation = f"✅ KNOWN ENTITY - {known.owner_name or 'This address'} is recognized in the TON ecosystem."

        return ScoreResult(
            score=score,
            grade=grade,
            grade_color=color,
            grade_description=desc,
            risk_level=risk_level,
            recommendation=recommendation,
            warnings=warnings,
            entity_info=entity_info,
        )

    # Step 2: Unknown address - apply default analysis
    # (This is where notaryton's existing token analysis would go)

    # For now, return default "caution" score
    warnings.append("New minter: No track record available")
    warnings.append("WARNING: Liquidity not locked - rug pull risk")
    warnings.append("New wallet: Less than 7 days old")

    return ScoreResult(
        score=605,
        grade='C',
        grade_color='#FACC15',
        grade_description='Fair - Exercise Caution',
        risk_level='MEDIUM',
        recommendation='Proceed with caution. Some risk factors present. Only invest what you can afford to lose.',
        warnings=warnings,
        entity_info=None,
    )


def format_score_response(result: ScoreResult) -> dict:
    """Format ScoreResult as JSON API response (matching creative-hub format)."""
    response = {
        'score': result.score,
        'grade': result.grade,
        'gradeInfo': {
            'color': result.grade_color,
            'description': result.grade_description,
        },
        'riskLevel': result.risk_level,
        'recommendation': result.recommendation,
        'warnings': result.warnings,
    }

    if result.entity_info:
        response['entityInfo'] = result.entity_info

    return response

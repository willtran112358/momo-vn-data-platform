-- dim_user_scd2.sql — Slowly Changing Dimension (Type 2) for MoMo users.
-- dbt incremental model. Point-in-time correctness is critical: credit/fraud
-- models must join "the user as they were at decision time", not as they are now.
--
-- Grain: one row per (user_id, version). is_current flags the live version.

{{ config(
    materialized='incremental',
    unique_key='user_sk',
    incremental_strategy='merge'
) }}

with source as (

    select
        user_id,
        kyc_tier,
        province,
        declared_income,
        is_income_imputed,
        updated_at
    from {{ ref('silver_wallet_user') }}
    {% if is_incremental() %}
      where updated_at > (select coalesce(max(valid_from), '1900-01-01') from {{ this }})
    {% endif %}

),

-- Hash the tracked attributes to detect a real change vs a no-op update.
hashed as (
    select
        *,
        {{ dbt_utils.generate_surrogate_key([
            'kyc_tier', 'province', 'declared_income', 'is_income_imputed'
        ]) }} as attr_hash
    from source
),

versioned as (
    select
        {{ dbt_utils.generate_surrogate_key(['user_id', 'updated_at']) }} as user_sk,
        user_id,
        kyc_tier,
        province,
        declared_income,
        is_income_imputed,
        attr_hash,
        updated_at                                   as valid_from,
        lead(updated_at) over (
            partition by user_id order by updated_at
        )                                            as next_change_at
    from hashed
)

select
    user_sk,
    user_id,
    kyc_tier,
    province,
    declared_income,
    is_income_imputed,
    valid_from,
    coalesce(next_change_at, timestamp '9999-12-31 00:00:00') as valid_to,
    (next_change_at is null)                                  as is_current
from versioned

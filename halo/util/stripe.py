import logging
from flask import current_app
import stripe
from models import User

assert hasattr(User, 'stripe_customer_id')
assert hasattr(User, 'plan')

# TODO: what is the value of customer.subscription.plan when not subscribed?
# TODO: also store stripe subscription start date (and end dates)?

# currently only supports stripe subscriptions (not one-off purchases)
# stripe does not allow customers to have multiple subscriptions

def stripe_sync(user, stripe_plan, plan, token=None):
    """Will update stripe with user data including subscribing or
    unsubscribing to plans. May change user so remember to save it after.
    stripe_plan is the plan id in stripe, plan is the plan name that will
    be associated with the user entity.
    """
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    if user.stripe_customer_id:
        customer = stripe.Customer.retrieve(user.stripe_customer_id)

        # update stripe customer if necessary
        if customer.email != user.email or customer.description != user.name:
            customer.email = user.email
            customer.description = user.name
            customer.save()

        if customer.subscription:
            current_plan = customer.subscription.plan.id
        else:
            current_plan = None

        if stripe_plan != current_plan:
            if stripe_plan is None:
                customer.cancel_subscription()
            else:
                assert token, 'A stripe token is required to change plan'
                customer.update_subscription(card=token, plan=stripe_plan)

            user.plan = plan

    elif stripe_plan != None:
        assert token, 'A stripe token is required to start a new plan'

        # user is a first time customer, so create stripe customer
        customer = stripe.Customer.create(
            email=user.email,
            description=user.name,
            plan=stripe_plan,
            card=token,
        )
        user.stripe_customer_id = customer.id
        user.plan = plan

    else:
        # user is not an existing stripe customer and is not trying
        # to start a plan
        pass

def stripe_delete(user):
    """Deletes the stripe user (may change user, so remember to save it)
    """
    if not user.stripe_customer_id:
        return

    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    customer = stripe.Customer.retrieve(user.stripe_customer_id)
    if customer.subscription:
        customer.cancel_subscription() # probably unecessary
    customer.delete()

    user.plan = None
    user.stripe_customer_id = None

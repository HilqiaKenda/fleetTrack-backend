import json
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from service.payment.exception_handler import PaymentError, ProviderNotFoundError
from service.payment.main import PaymentService


# Create your views here.

@csrf_exempt
def deposit_view(request):
    """
    Dammy deposit to test deposit payment
    """
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Only POST method allowed"},
            status=405
        )
    
    try:
        body = json.loads(request.body)

        provider = body.get("provider")
        amount = body.get("amount")
        tx_ref = body.get("tx_ref")
        user = body.get("user", {})
        options = body.get("options", {})
        # Basic validation
        if not provider or not amount or not tx_ref:
            return JsonResponse(
                {"success": False, "error": "provider, amount and tx_ref are required"},
                status=400
            )

        if not all(k in user for k in ("email", "phone", "name")):
            return JsonResponse(
                {"success": False, "error": "user must include email, phone, name"},
                status=400
            )

        payment_service = PaymentService(provider)

        result = payment_service.deposit(
            amount=Decimal(str(amount)),
            user=user,
            tx_ref=tx_ref,
            **options
        )

        return JsonResponse(result.to_dict(), status=200)

    except ProviderNotFoundError as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=400
        )

    except PaymentError as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=400
        )

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )

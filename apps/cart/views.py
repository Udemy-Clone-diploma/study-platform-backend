from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.cart.models import Cart
from apps.cart.serializers import CartItemAddSerializer, CartSerializer
from apps.cart.services import CartService
from apps.users.permissions import IsStudent


@extend_schema(tags=["Cart"])
class CartViewSet(viewsets.GenericViewSet):
    queryset = Cart.objects.none()
    permission_classes = [IsStudent]
    serializer_class = CartSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "add_item":
            return CartItemAddSerializer
        return CartSerializer

    @extend_schema(
        summary="Retrieve the current student's cart",
        responses={200: CartSerializer},
    )
    def list(self, request, *args, **kwargs):
        cart = CartService.get_current_cart(request.user)
        data = CartService.serialize_cart(cart, self.get_serializer_context())
        return Response(data)

    @extend_schema(
        summary="Add a course to the current student's cart",
        request=CartItemAddSerializer,
        responses={201: CartSerializer},
    )
    @action(detail=False, methods=["post"], url_path="items")
    def add_item(self, request, *args, **kwargs):
        data = CartService.add_item_from_data(
            request.data,
            request.user,
            self.get_serializer_context(),
        )
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Remove a course from the current student's cart",
        responses={200: CartSerializer},
    )
    @action(detail=False, methods=["delete"], url_path=r"items/(?P<course_id>[^/.]+)")
    def remove_item(self, request, course_id=None, *args, **kwargs):
        data = CartService.remove_item_from_data(
            course_id,
            request.user,
            self.get_serializer_context(),
        )
        return Response(data)

    @extend_schema(
        summary="Clear the current student's cart",
        responses={200: CartSerializer},
    )
    @action(detail=False, methods=["delete"], url_path="clear")
    def clear(self, request, *args, **kwargs):
        data = CartService.clear_current_cart(
            request.user,
            self.get_serializer_context(),
        )
        return Response(data)

from django import forms


class CafeteriaWeeklyReservationForm(forms.Form):

    def __init__(self, *args, menus=None, **kwargs):
        super().__init__(*args, **kwargs)

        if menus is None:
            return

        for menu in menus:

            field_name = f"menu_{menu.id}"

            self.fields[field_name] = forms.BooleanField(
                required=False,
                label=(
                    f"{menu.get_day_display()} - "
                    f"{menu.food_name} - "
                    f"{menu.price} تومان"
                ),
            )



from .models import CafeteriaReservation


class CafeteriaReceiptUploadForm(forms.ModelForm):

    class Meta:
        model = CafeteriaReservation

        fields = [
            "receipt_image",
        ]

        labels = {
            "receipt_image": "تصویر فیش واریزی",
        }
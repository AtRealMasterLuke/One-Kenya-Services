from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render

from .forms import PhoneLoginForm, RegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Your account is ready. You can now report a problem.")
        return redirect("request_new")
    return render(request, "accounts/register.html", {"form": form})


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = PhoneLoginForm
    redirect_authenticated_user = True

from django.shortcuts import render


def show_main(request):
    return render(request, 'index.html')


def sign_in(request):
    return render(request, 'sign_in.html')


def register(request):
    return render(request, 'register.html')

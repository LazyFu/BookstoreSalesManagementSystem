# catalog/forms.py
from django.contrib.auth.forms import UserCreationForm, UsernameField, SetPasswordForm
from django.contrib.auth.models import User
from django import forms

from .models import Customer, Order


class CustomUserCreationForm(UserCreationForm):
    phone = forms.CharField(
        label="手机号码",
        max_length=20,
        required=True,
    )

    class Meta:
        model = User
        fields = ("username",)
        field_classes = {'username': UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'username' in self.fields:
            self.fields['username'].label = "用户名"
            self.fields['username'].help_text = ""

        if 'password1' in self.fields:
            self.fields['password1'].label = "密码"
            self.fields['password1'].help_text = ""

        if 'password2' in self.fields:
            self.fields['password2'].label = "确认密码"
            self.fields['password2'].help_text = '请再次输入相同的密码以确认。'


class CheckoutForm(forms.Form):
    name = forms.CharField(label='姓名', max_length=100, required=True,
                           widget=forms.TextInput(attrs={'class': 'your-css-class-for-name'}))  # 可选：添加CSS类
    phone = forms.CharField(
        label='电话',
        max_length=20,
        required=True,
        widget=forms.TextInput(attrs={
            'pattern': '[0-9]{11,13}',
            'title': '请输入有效的电话号码 (例如11位手机号)',
            'class': 'your-css-class-for-phone'  # 可选：添加CSS类
        })
    )
    status = forms.ChoiceField(
        label='支付状态',
        choices=Order.STATUS_CHOICES,  # 使用 Order 模型中定义的选项
        required=True,
        initial='U',  # 默认初始值为 'U' (未支付)
        widget=forms.Select(attrs={'class': 'form-control-checkout'})  # 可选：添加CSS类
    )


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'vip_status']


class UsernameInputForm(forms.Form):
    username = forms.CharField(
        label="用户名",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': '请输入您的用户名'})
    )

    def clean_username(self):
        username = self.cleaned_data.get('username')
        # 检查用户是否存在
        if not User.objects.filter(username=username).exists():
            raise forms.ValidationError("该用户名不存在。")
        return username


class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)  # 调用父类的 __init__

        self.fields['new_password1'].label = "新密码"
        self.fields['new_password1'].help_text = ''

        self.fields['new_password2'].label = "确认新密码"
        self.fields['new_password2'].help_text = "请再次输入相同的新密码以确认。"

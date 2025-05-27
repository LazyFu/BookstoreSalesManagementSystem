# catalog/forms.py
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django import forms


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)  # 通常 UserCreationForm 会自动处理密码字段
        field_classes = {'username': UsernameField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 修改或移除 username 字段的帮助文字 (可选)
        if 'username' in self.fields:
            # self.fields['username'].help_text = '自定义的用户名帮助文字'
            self.fields['username'].help_text = ''  # 设为空字符串以移除

        # 移除 password1 (密码) 字段的帮助文字 (那些列出的规则)
        # Django 会从 AUTH_PASSWORD_VALIDATORS 配置中获取这些帮助文字
        # 将 help_text 设为空字符串可以阻止它们在 {{ field.help_text }} 中显示
        if 'password1' in self.fields:
            self.fields['password1'].help_text = ''

        # 修改或移除 password2 (确认密码) 字段的帮助文字
        if 'password2' in self.fields:
            # self.fields['password2'].help_text = '请再次输入相同的密码。' # 可以自定义
            self.fields['password2'].help_text = ''  # 设为空字符串以移除


class CheckoutForm(forms.Form):
    name = forms.CharField(label='姓名', max_length=100, required=True)
    phone = forms.CharField(label='电话', max_length=20, required=True)  # 之前模型里是 max_length=20

    # 用于创建账户的字段 (非必填，除非勾选了创建账户)
    email = forms.EmailField(label='邮箱 (可选，用于创建账户)', required=False)
    password = forms.CharField(label='设置密码 (可选，用于创建账户)', widget=forms.PasswordInput, required=False,
                               min_length=8)
    confirm_password = forms.CharField(label='确认密码 (可选)', widget=forms.PasswordInput, required=False)
    create_account = forms.BooleanField(label='为此订单创建一个账户并享受会员服务', required=False)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        create_account = self.cleaned_data.get('create_account')
        if create_account:
            if not email:
                raise forms.ValidationError("如果您选择创建账户，邮箱是必填的。")
            if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
                raise forms.ValidationError("此邮箱已被注册或用作用户名，请尝试登录或使用其他邮箱。")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        create_account = self.cleaned_data.get('create_account')
        if create_account and not password:
            raise forms.ValidationError("如果您选择创建账户，密码是必填的。")
        # 你可以在这里添加更复杂的密码强度验证逻辑
        return password

    def clean(self):  # 整个表单的清理方法，用于跨字段验证
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        create_account = cleaned_data.get('create_account')

        if create_account and password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "两次输入的密码不一致。")

        return cleaned_data

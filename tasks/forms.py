"""Forms for the To-Do List app."""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, Profile, Task


class TaskForm(forms.ModelForm):
    """Create/edit form for a Task. Server-side validation is enforced by
    Django's form layer regardless of what the client-side JS does.

    The category choices are scoped to the requesting user — pass
    ``user=request.user`` when instantiating so one user is never shown (or
    able to assign) another user's categories.
    """

    does_repeat = forms.ChoiceField(
        choices=Task.Recurrence.choices,
        required=False,
        initial=Task.Recurrence.NONE,
        label='Does this task repeat?',
    )

    class Meta:
        model = Task
        fields = [
            'title', 'description', 'category', 'priority', 'due_date', 'due_time',
            'does_repeat', 'recurrence_interval', 'recurrence_end_date',
            'reminder_offset', 'attachment',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. Finish project documentation',
                'maxlength': 200,
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Add a little context (optional)',
                'rows': 3,
                'maxlength': 1000,
            }),
            'category': forms.Select(),
            'priority': forms.Select(),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'due_time': forms.TimeInput(attrs={'type': 'time'}),
            'recurrence_interval': forms.NumberInput(attrs={'min': 1, 'max': 365}),
            'recurrence_end_date': forms.DateInput(attrs={'type': 'date'}),
            'reminder_offset': forms.Select(),
        }
        labels = {
            'recurrence_interval': 'Repeat every N days (for Custom)',
            'recurrence_end_date': 'Stop repeating after',
            'reminder_offset': 'Remind me',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(user=user) if user else Category.objects.none()
        self.fields['category'].required = False
        self.fields['attachment'].required = False
        if self.instance and self.instance.pk:
            self.fields['does_repeat'].initial = self.instance.recurrence_type

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError('Please give the task a title.')
        return title

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment and hasattr(attachment, 'size') and attachment.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Attachment must be smaller than 5MB.')
        return attachment

    def save(self, commit=True):
        task = super().save(commit=False)
        recurrence = self.cleaned_data.get('does_repeat') or Task.Recurrence.NONE
        task.recurrence_type = recurrence
        task.is_recurring = recurrence != Task.Recurrence.NONE
        if commit:
            task.save()
        return task


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Fitness', 'maxlength': 50}),
            'color': forms.TextInput(attrs={'type': 'color'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        qs = Category.objects.filter(user=self.user, name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('You already have a category with this name.')
        return name


class ProfileForm(forms.ModelForm):
    """Settings-page preferences, persisted per-user."""

    class Meta:
        model = Profile
        fields = ['theme_preference', 'default_priority', 'default_view', 'default_sort', 'reminders_enabled']
        widgets = {
            'default_priority': forms.Select(choices=Task.Priority.choices),
            'default_sort': forms.Select(choices=[
                ('due_date', 'Due date'), ('priority', 'Priority'),
                ('created', 'Recently created'), ('updated', 'Recently updated'),
            ]),
        }


class ProfileEmailForm(forms.ModelForm):
    """A deliberately small form: users may update their email address, but
    not their username or other sensitive account details from this page."""

    class Meta:
        model = User
        fields = ['email']
        widgets = {'email': forms.EmailInput()}

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class RegisterForm(UserCreationForm):
    """Registration form: username, email, password, confirm password."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

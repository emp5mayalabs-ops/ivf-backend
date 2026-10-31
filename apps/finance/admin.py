from django.contrib import admin
from .models import Account, JournalEntry, JournalEntryLine

class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0
    readonly_fields = ('account', 'amount', 'is_debit')

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_type', 'source_id', 'entry_date', 'status')
    list_filter = ('source_type', 'status')
    search_fields = ('source_id',)
    inlines = [JournalEntryLineInline]

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'type', 'is_clearing')
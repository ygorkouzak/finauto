-- migrations/002_telefone_transacoes.sql
-- Adiciona coluna `telefone` à tabela transacoes.
-- Guarda o número de quem enviou a mensagem via WhatsApp.
-- Rodar uma única vez no SQL Editor do Supabase.

alter table public.transacoes
    add column if not exists telefone text;

comment on column public.transacoes.telefone
    is 'Número do WhatsApp que originou o cadastro (ex: +5562...). Nulo para cadastros manuais.';

-- migrations/003_responsavel_por_telefone.sql
-- Trigger que preenche `responsavel` automaticamente a partir do `telefone`
-- nos INSERTs e UPDATEs da tabela transacoes.
-- Rodar uma única vez no SQL Editor do Supabase.

create or replace function public.resolver_responsavel_por_telefone()
returns trigger language plpgsql as $$
begin
    if new.telefone is not null then
        new.responsavel := case new.telefone
            when '+5562981027386' then 'Y'
            when '+5562999279000' then 'M'
            else coalesce(new.responsavel, 'Y')
        end;
    end if;
    return new;
end;
$$;

drop trigger if exists trg_responsavel_por_telefone on public.transacoes;
create trigger trg_responsavel_por_telefone
    before insert or update of telefone
    on public.transacoes
    for each row
    execute function public.resolver_responsavel_por_telefone();

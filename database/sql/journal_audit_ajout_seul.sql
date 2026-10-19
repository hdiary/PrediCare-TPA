-- Journal d'audit en ajout seul (AI Act art. 12) : aucune ligne ne peut être modifiée ni supprimée.
-- À placer comme prochaine migration versionnée, après celle qui crée journal_audit.
-- Attention : une purge de rétention RGPD devra désactiver ce déclencheur de façon explicite
-- (ALTER TABLE journal_audit DISABLE TRIGGER ...) et être elle-même documentée.

CREATE OR REPLACE FUNCTION journal_audit_ajout_seul() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'journal_audit est en ajout seul : % interdit', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_audit_maj_suppr ON journal_audit;
CREATE TRIGGER trg_journal_audit_maj_suppr
    BEFORE UPDATE OR DELETE ON journal_audit
    FOR EACH ROW EXECUTE FUNCTION journal_audit_ajout_seul();

DROP TRIGGER IF EXISTS trg_journal_audit_vidage ON journal_audit;
CREATE TRIGGER trg_journal_audit_vidage
    BEFORE TRUNCATE ON journal_audit
    FOR EACH STATEMENT EXECUTE FUNCTION journal_audit_ajout_seul();

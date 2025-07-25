import logging
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from sqlmodel import (
    JSON,
    Column,
    Field,
    Relationship,
    Session,
    SQLModel,
    UniqueConstraint,
    select,
)

logger = logging.getLogger(__name__)


from sqlalchemy import JSON


class BaseModel(SQLModel):
    """Base model with common CRUD operations - Django-style ActiveRecord pattern"""

    @classmethod
    def create(cls, session: Session, **kwargs) -> "BaseModel":
        """Create and save a new instance"""
        instance = cls(**kwargs)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return instance

    @classmethod
    def get_by_id(cls, session: Session, id: int) -> Optional["BaseModel"]:
        """Get instance by ID"""
        return session.get(cls, id)

    @classmethod
    def get_all(cls, session: Session) -> List["BaseModel"]:
        """Get all instances"""
        statement = select(cls)
        return session.exec(statement).all()

    @classmethod
    def filter_by(cls, session: Session, **kwargs) -> List["BaseModel"]:
        """Filter instances by given criteria"""
        statement = select(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                statement = statement.where(getattr(cls, key) == value)
        return session.exec(statement).all()

    @classmethod
    def get_or_create(
        cls, session: Session, defaults=None, **kwargs
    ) -> tuple["BaseModel", bool]:
        """Get instance or create if it doesn't exist"""
        statement = select(cls)
        for key, value in kwargs.items():
            if hasattr(cls, key):
                statement = statement.where(getattr(cls, key) == value)

        instance = session.exec(statement).first()
        if instance:
            return instance, False
        else:
            create_kwargs = kwargs.copy()
            if defaults:
                create_kwargs.update(defaults)
            instance = cls.create(session, **create_kwargs)
            return instance, True

    def save(self, session: Session) -> "BaseModel":
        """Save current instance"""
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def update(self, session: Session, **kwargs) -> "BaseModel":
        """Update current instance"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.save(session)

    def delete(self, session: Session) -> None:
        """Delete current instance"""
        session.delete(self)
        session.commit()


class Aluno(BaseModel, table=True):
    id: Optional[int] = Field(
        default=None,  # Default to None for auto-increment
        primary_key=True,
    )

    # API:
    nome: str

    matricula: Optional[str] = None
    responsavel_id: Optional[int] = None

    cpf: Optional[str] = None
    sexo: Optional[str] = None
    data_nascimento: Optional[datetime] = None
    celular: Optional[str] = None
    email: Optional[str] = None
    url_foto: Optional[str] = None

    responsavel_secundario_id: Optional[int] = None
    filiacao_1_id: Optional[int] = None
    filiacao_2_id: Optional[int] = None
    cartao_acesso: Optional[str] = None
    unidade_id: Optional[int] = None
    tipo_liberacao: Optional[str] = None
    foto_data_hora_alteracao: Optional[datetime] = None
    # cartao_acesso_data_alteracao: Optional[datetime] = None

    responsaveis_adicionais_ids: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    id_turmas: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )

    # Relationships:
    cartoes_acesso: List["CartaoAcesso"] = Relationship(
        back_populates="aluno",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # Custom model-specific methods
    @classmethod
    def find_by_matricula(cls, session: Session, matricula: str) -> Optional["Aluno"]:
        """Find student by matricula"""
        statement = select(cls).where(cls.matricula == matricula)
        return session.exec(statement).first()

    @classmethod
    def find_by_cpf(cls, session: Session, cpf: str) -> Optional["Aluno"]:
        """Find student by CPF"""
        statement = select(cls).where(cls.cpf == cpf)
        return session.exec(statement).first()

    @classmethod
    def search_by_name(cls, session: Session, name_part: str) -> List["Aluno"]:
        """Search students by name (partial match)"""
        statement = select(cls).where(cls.nome.ilike(f"%{name_part}%"))
        return session.exec(statement).all()

    def add_cartao_acesso(self, session: Session, numeracao: str) -> "CartaoAcesso":
        """Add a new access card to this student"""
        cartao = CartaoAcesso.create(session, numeracao=numeracao, aluno_id=self.id)
        return cartao

    def get_active_cartoes(self, session: Session) -> List["CartaoAcesso"]:
        """Get all active access cards for this student"""
        return [cartao for cartao in self.cartoes_acesso if cartao.aluno_id == self.id]

    def get_recent_acessos(self, session: Session, days: int = 30) -> List["Acesso"]:
        """Get recent access records for this student"""
        cutoff_date = date.today() - timedelta(days=days)
        cartao_ids = [cartao.id for cartao in self.cartoes_acesso]
        if not cartao_ids:
            return []

        statement = select(Acesso).where(
            Acesso.cartao_acesso_id.in_(cartao_ids), Acesso.date >= cutoff_date
        )
        return session.exec(statement).all()


class CartaoAcesso(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # API:
    # TODO: Deveríamos garantir que sempre será com 0s à esquerda !
    numeracao: str = Field(unique=True)  # str(5) ou str(16)

    # Relationships:
    aluno_id: Optional[int] = Field(default=None, foreign_key="aluno.id")
    aluno: Optional[Aluno] = Relationship(back_populates="cartoes_acesso")

    acessos: List["Acesso"] = Relationship(back_populates="cartao_acesso")

    @staticmethod
    def from_string(data: str) -> Optional["CartaoAcesso"]:
        """
        Creates a CartaoAcesso instance from a string.
        """
        try:
            numeracao = data[:16].strip()
            return CartaoAcesso(numeracao=numeracao)
        except Exception as e:
            logger.error(f"Error parsing CartaoAcesso from string: {e}")
            return None

    @classmethod
    def find_by_numeracao(
        cls, session: Session, numeracao: str
    ) -> Optional["CartaoAcesso"]:
        """Find access card by numeracao"""
        statement = select(cls).where(cls.numeracao == numeracao)
        return session.exec(statement).first()

    @classmethod
    def get_unassigned(cls, session: Session) -> List["CartaoAcesso"]:
        """Get all unassigned access cards"""
        statement = select(cls).where(cls.aluno_id.is_(None))
        return session.exec(statement).all()

    def get_recent_acessos(self, session: Session, days: int = 30) -> List["Acesso"]:
        """Get recent access records for this card"""
        cutoff_date = date.today() - timedelta(days=days)
        statement = select(Acesso).where(
            Acesso.cartao_acesso_id == self.id, Acesso.date >= cutoff_date
        )
        return session.exec(statement).all()

    def assign_to_aluno(self, session: Session, aluno_id: int) -> "CartaoAcesso":
        """Assign this card to a student"""
        return self.update(session, aluno_id=aluno_id)

    def unassign(self, session: Session) -> "CartaoAcesso":
        """Unassign this card from any student"""
        return self.update(session, aluno_id=None)


class Acesso(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # API:
    marcacao: str  # "010"=Entrada, "011"=Saída
    date: date  # dd/mm/yy ou dd/mm/yyyy
    time: time  # hh:mm
    catraca: str  # str(2) = 01, 02, 03, ..., 99
    # "sequencial": # str(10)

    # Extra Fields:
    synced: Optional[bool] = Field(default=False)

    # Relationships:
    cartao_acesso_id: Optional[int] = Field(default=None, foreign_key="cartaoacesso.id")
    cartao_acesso: Optional[CartaoAcesso] = Relationship(back_populates="acessos")

    # Unique:
    __table_args__ = (
        UniqueConstraint(
            "marcacao",
            "date",
            "time",
            "catraca",
            "cartao_acesso_id",
            name="uq_acesso_marcacao_date_time_cat_cartao",
            comment="Unique constraint for Acesso table",
        ),
    )

    # Custom model-specific methods
    @classmethod
    def get_unsynced(cls, session: Session) -> List["Acesso"]:
        """Get all unsynced access records"""
        statement = select(cls).where(cls.synced == False)
        return session.exec(statement).all()

    @classmethod
    def get_by_date_range(
        cls, session: Session, start_date: "date", end_date: "date"
    ) -> List["Acesso"]:
        """Get access records within date range"""
        statement = select(cls).where(cls.date >= start_date, cls.date <= end_date)
        return session.exec(statement).all()

    @classmethod
    def get_by_cartao(cls, session: Session, cartao_id: int) -> List["Acesso"]:
        """Get all access records for a specific card"""
        statement = select(cls).where(cls.cartao_acesso_id == cartao_id)
        return session.exec(statement).all()

    def mark_synced(self, session: Session) -> "Acesso":
        """Mark this access record as synced"""
        return self.update(session, synced=True)

    @classmethod
    def bulk_mark_synced(cls, session: Session, access_ids: List[int]) -> None:
        """Mark multiple access records as synced"""
        statement = select(cls).where(cls.id.in_(access_ids))
        records = session.exec(statement).all()
        for record in records:
            record.synced = True
            session.add(record)
        session.commit()

    @classmethod
    def get_entries_exits_by_date(cls, session: Session, target_date: "date") -> dict:
        """Get count of entries and exits for a specific date"""
        statement = select(cls).where(cls.date == target_date)
        records = session.exec(statement).all()

        entries = sum(1 for r in records if r.marcacao == "010")
        exits = sum(1 for r in records if r.marcacao == "011")

        return {"entries": entries, "exits": exits, "total": len(records)}

    def __repr__(self):
        return (
            f"Acesso(id={self.id}, marcacao='{self.marcacao}', date='{self.date}', "
            f"time='{self.time}', catraca='{self.catraca}', cartao_acesso_id={self.cartao_acesso_id})"
        )

    def __str__(self):
        # try:
        #     cartao_info = self.cartao_acesso.numeracao if self.cartao_acesso else "N/A"
        # except (AttributeError, Exception):
        #     cartao_info = str(self.cartao_acesso_id)

        return (
            f"Acesso {self.id}: {self.marcacao} on {self.date} at {self.time} "
            f"from cartao_id: {self.cartao_acesso_id}) (Catraca: {self.catraca})"
        )

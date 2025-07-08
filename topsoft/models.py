import logging
from datetime import date, datetime, time
from typing import List, Optional

from sqlmodel import JSON, Column, Field, Relationship, SQLModel, UniqueConstraint

logger = logging.getLogger(__name__)


from sqlalchemy import JSON


class Aluno(SQLModel, table=True):
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


class CartaoAcesso(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # API:
    # TODO: Deveríamos garantir que sempre será com 0s à esquerda !
    numeracao: str = Field(unique=True)  # str(5) ou str(16)

    # Relationships:
    aluno_id: Optional[int] = Field(default=None, foreign_key="aluno.id")
    aluno: Optional[Aluno] = Relationship(back_populates="cartoes_acesso")

    acessos: List["Acesso"] = Relationship(back_populates="cartao_acesso")


class Acesso(SQLModel, table=True):
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

    def __repr__(self):
        return (
            f"Acesso(id={self.id}, marcacao='{self.marcacao}', date='{self.date}', "
            f"time='{self.time}', catraca='{self.catraca}', cartao_acesso_id={self.cartao_acesso_id})"
        )

    def __str__(self):
        return (
            f"Acesso {self.id}: {self.marcacao} on {self.date} at {self.time} "
            f"from cartao {self.cartao_acesso_id} (Catraca: {self.catraca})"
        )

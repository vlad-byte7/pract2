"""Получает прямые зависимости из POM в Maven-репозитории."""

import re
from dataclasses import dataclass, field
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen
from xml.etree import ElementTree

from config import MAVEN_PACKAGE


PROPERTY = re.compile(r"\$\{([^{}]+)\}")
MANAGED = "{*}dependencyManagement/{*}dependencies/{*}dependency"
DIRECT = "{*}dependencies/{*}dependency"
MANAGED_FIELDS = ("version", "scope", "optional")
RUNTIME_SCOPES = ("compile", "runtime")
HTTP_TIMEOUT = 10


class MavenError(RuntimeError):
    """Сообщает о проблеме с получением или разбором POM."""


@dataclass
class PomModel:
    """Хранит данные проекта для наследования и подстановки свойств."""

    properties: dict = field(default_factory=dict)
    managed: dict = field(default_factory=dict)
    dependencies: dict = field(default_factory=dict)


def pom_url(repository, package):
    """Строит адрес POM по координатам Maven-пакета."""
    if not MAVEN_PACKAGE.fullmatch(package):
        raise MavenError(f"некорректные координаты POM: {package}")
    group, artifact, version = package.split(":")
    if not all(group.split(".")) or {artifact, version} & {".", ".."}:
        raise MavenError(f"некорректные координаты POM: {package}")
    group_path = group.replace(".", "/")
    url = urlsplit(repository)
    path = f"{url.path.rstrip('/')}/{group_path}/{artifact}/{version}"
    pom_path = f"{path}/{artifact}-{version}.pom"
    return url._replace(path=pom_path, fragment="").geturl()


def fetch_pom(url):
    """Загружает и разбирает POM стандартными средствами Python."""
    try:
        with urlopen(url, timeout=HTTP_TIMEOUT) as response:
            root = ElementTree.parse(response).getroot()
    except (URLError, OSError, ValueError, ElementTree.ParseError) as error:
        raise MavenError(f"не удалось прочитать POM {url}: {error}") from error
    if root.tag.rsplit("}", 1)[-1] != "project":
        raise MavenError(f"ожидался элемент project в POM {url}")
    return root


def value_of(element, name):
    """Возвращает текст дочернего элемента XML с любым пространством имён."""
    return (element.findtext(f"{{*}}{name}") or "").strip()


def interpolate(value, properties, stack=()):
    """Подставляет значения свойств Maven и останавливается при цикле."""

    def replace(match):
        name = match[1]
        if name in stack or name not in properties:
            return match[0]
        return interpolate(properties[name], properties, (*stack, name))

    return PROPERTY.sub(replace, value)


def dependency_key(node, properties):
    """Возвращает ключ для поиска зависимости и её настроек."""
    fields = ("groupId", "artifactId", "type", "classifier")
    group, artifact, kind, classifier = (
        interpolate(value_of(node, name), properties) for name in fields
    )
    if not group or not artifact or PROPERTY.search(group + artifact):
        raise MavenError(f"не удалось определить координаты {group}:{artifact}")
    return group, artifact, kind or "jar", classifier


def project_properties(pom, package, parent):
    """Собирает свойства текущего POM и координаты для подстановок."""
    properties = parent.properties.copy()
    for node in pom.findall("{*}properties/*"):
        properties[node.tag.rsplit("}", 1)[-1]] = (node.text or "").strip()

    keys = ("groupId", "artifactId", "version")
    for key, value in zip(keys, package.split(":")):
        properties[f"project.{key}"] = value
        properties[f"pom.{key}"] = value
    return properties


def parent_model(pom, repository, stack, cache):
    """Читает родительский POM, когда он указан в описании проекта."""
    parent = pom.find("{*}parent")
    if parent is None:
        return PomModel()
    keys = ("groupId", "artifactId", "version")
    local = project_properties(pom, stack[-1], PomModel())
    coordinates = (interpolate(value_of(parent, key), local) for key in keys)
    package = ":".join(coordinates)
    return read_model(repository, package, stack, cache)


def managed_dependencies(pom, repository, properties, parent, stack, cache):
    """Собирает настройки версий из проекта, родителя и импортируемых BOM."""
    managed = parent.managed.copy()
    imports = []
    for node in pom.findall(MANAGED):
        key = dependency_key(node, properties)
        scope = interpolate(value_of(node, "scope"), properties)
        if key[2] == "pom" and scope == "import":
            version = interpolate(value_of(node, "version"), properties)
            imports.append(":".join((key[0], key[1], version)))
        else:
            managed[key] = node

    for package in imports:
        model = read_model(repository, package, stack, cache)
        for key, entry in model.managed.items():
            settings = {
                name: managed_value(entry, name, model.properties)
                for name in MANAGED_FIELDS
            }
            managed.setdefault(key, settings)
    return managed


def managed_value(entry, name, properties):
    """Берёт значение из объявления или из уже обработанного BOM."""
    if isinstance(entry, dict):
        return entry[name]
    return interpolate(value_of(entry, name), properties)


def dependency_value(node, model, key, name):
    """Использует управляемое значение, если оно отсутствует в зависимости."""
    value = interpolate(value_of(node, name), model.properties)
    if not value and key in model.managed:
        return managed_value(model.managed[key], name, model.properties)
    return value


def read_model(repository, package, stack, cache):
    """Загружает модель POM и проверяет циклы родительских POM и BOM."""
    if package in stack:
        chain = " -> ".join((*stack, package))
        raise MavenError(f"циклическая ссылка между POM: {chain}")
    if package in cache:
        return cache[package]

    stack = (*stack, package)
    pom = fetch_pom(pom_url(repository, package))
    parent = parent_model(pom, repository, stack, cache)
    properties = project_properties(pom, package, parent)
    managed = managed_dependencies(
        pom, repository, properties, parent, stack, cache
    )
    direct = parent.dependencies.copy()
    for node in pom.findall(DIRECT):
        direct[dependency_key(node, properties)] = node

    model = PomModel(properties, managed, direct)
    cache[package] = model
    return model


def dependency_coordinate(node, model, key):
    """Собирает координаты прямой зависимости и разрешает её версию."""
    version = dependency_value(node, model, key, "version")
    package = ":".join(key[:2])
    if not version or PROPERTY.search(version):
        raise MavenError(f"не удалось определить версию зависимости {package}")
    return f"{package}:{version}"


def direct_dependencies(repository, package):
    """Возвращает координаты прямых зависимостей выбранного пакета."""
    model = read_model(repository, package, (), {})
    return [
        dependency_coordinate(node, model, key)
        for key, node in model.dependencies.items()
    ]


def runtime_dependencies(repository, package, cache):
    """Выбирает обязательные зависимости с областью compile или runtime."""
    model = read_model(repository, package, (), cache)
    dependencies = []
    for key, node in model.dependencies.items():
        scope = dependency_value(node, model, key, "scope") or "compile"
        optional = dependency_value(node, model, key, "optional")
        if scope in RUNTIME_SCOPES and optional.lower() != "true":
            dependencies.append(dependency_coordinate(node, model, key))
    return dependencies

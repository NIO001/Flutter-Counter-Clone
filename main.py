import flet as ft
import requests
import os
import json
from packaging import version
import asyncio
import android_helper
from pathlib import Path
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações do app
GITHUB_REPO = "NIO001/update"
VERSION = "1.0.0"
APP_NAME = "ContadorApp"
UPDATE_DIR = "/storage/emulated/0/Download"  # Diretório de download no Android

# Função para solicitar permissões no Android
async def request_android_permissions():
    try:
        from jnius import autoclass
        
        # Classes do Android necessárias
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Build = autoclass('android.os.Build')
        Context = autoclass('android.content.Context')
        PackageManager = autoclass('android.content.pm.PackageManager')

        # Permissões necessárias
        permissions = [
            "android.permission.INTERNET",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.REQUEST_INSTALL_PACKAGES"
        ]

        # Verifica se é Android e versão >= 23 (M)
        if Build.VERSION.SDK_INT >= 23:
            activity = PythonActivity.mActivity
            for permission in permissions:
                if activity.checkSelfPermission(permission) != PackageManager.PERMISSION_GRANTED:
                    activity.requestPermissions([permission], 1)
                    
    except Exception as e:
        logger.error(f"Erro ao solicitar permissões: {e}")
        pass  # Não é Android ou erro ao solicitar permissões

class UpdateManager:
    def __init__(self):
        self.github_api = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        
    async def check_for_updates(self):
        try:
            response = requests.get(self.github_api)
            if response.status_code == 200:
                release_data = response.json()
                latest_version = release_data["tag_name"].replace("v", "")
                if version.parse(latest_version) > version.parse(VERSION):
                    # Encontrar o asset APK
                    apk_asset = next(
                        (asset for asset in release_data["assets"] 
                         if asset["name"].endswith(".apk")), None
                    )
                    if apk_asset:
                        return True, latest_version, apk_asset["browser_download_url"]
            return False, VERSION, None
        except Exception as e:
            logger.error(f"Erro ao verificar atualizações: {e}")
            return False, VERSION, None

    async def download_update(self, download_url, progress_callback):
        try:
            response = requests.get(download_url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            if not os.path.exists(UPDATE_DIR):
                os.makedirs(UPDATE_DIR)
                
            apk_path = os.path.join(UPDATE_DIR, f"{APP_NAME}_update.apk")
            
            block_size = 1024
            downloaded = 0
            
            with open(apk_path, 'wb') as file:
                for data in response.iter_content(block_size):
                    downloaded += len(data)
                    file.write(data)
                    progress = int((downloaded / total_size) * 100)
                    await progress_callback(progress)
                    
            return apk_path
        except Exception as e:
            logger.error(f"Erro ao baixar atualização: {e}")
            return None

def main(page: ft.Page):
    page.title = "Contador com Auto-Update"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    
    # Componentes da UI
    number = ft.Text("0", size=30)
    update_status = ft.Text("", color=ft.colors.GREEN)
    progress_bar = ft.ProgressBar(width=300, visible=False)
    download_button = ft.ElevatedButton(
        "Baixar Atualização",
        visible=False,
        on_click=lambda e: asyncio.create_task(download_and_install_update())
    )

    update_manager = UpdateManager()

    async def check_update(e):
        update_status.value = "Verificando atualizações..."
        page.update()
        
        has_update, latest, download_url = await update_manager.check_for_updates()
        
        if has_update:
            update_status.value = f"Nova versão disponível: {latest}"
            update_status.color = ft.colors.GREEN
            download_button.visible = True
            download_button.data = download_url
        else:
            update_status.value = "App está atualizado!"
            update_status.color = ft.colors.BLUE
            download_button.visible = False
        page.update()

    async def download_and_install_update():
        try:
            progress_bar.visible = True
            download_button.disabled = True
            page.update()

            async def update_progress(progress):
                progress_bar.value = progress / 100
                page.update()

            apk_path = await update_manager.download_update(
                download_button.data,
                update_progress
            )

            if apk_path:
                update_status.value = "Download concluído. Iniciando instalação..."
                page.update()
                
                # Instalar APK usando o android_helper
                success = await android_helper.install_apk(apk_path)
                
                if success:
                    update_status.value = "Instalação iniciada!"
                else:
                    update_status.value = "Erro na instalação. Tente manualmente."
            else:
                update_status.value = "Erro no download. Tente novamente."
                
        except Exception as e:
            update_status.value = f"Erro: {str(e)}"
            logger.error(f"Erro no processo de atualização: {e}")
        
        finally:
            progress_bar.visible = False
            download_button.disabled = False
            page.update()

    def increment(e):
        number.value = str(int(number.value) + 1)
        page.update()

    def decrement(e):
        number.value = str(int(number.value) - 1)
        page.update()

    # Layout
    page.add(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("-", on_click=decrement),
                        number,
                        ft.ElevatedButton("+", on_click=increment),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.ElevatedButton(
                    "Verificar Atualizações",
                    on_click=lambda e: asyncio.create_task(check_update(e)),
                ),
                update_status,
                progress_bar,
                download_button,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

if __name__ == "__main__":
    try:
        asyncio.run(request_android_permissions())
    except Exception as e:
        logger.error(f"Erro ao solicitar permissões: {e}")
    finally:
        ft.app(target=main, view=ft.AppView.FLET_APP) 
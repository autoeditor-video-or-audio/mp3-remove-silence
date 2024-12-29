# MP3 Remove Silence

Este projeto automatiza a remoção de silêncios em arquivos MP3, permitindo a edição eficiente e o gerenciamento de mídia. Após a edição, os arquivos são armazenados e organizados em buckets no MinIO, proporcionando uma solução prática e otimizada.

## Funcionalidades principais:

- **Edição automática de MP3**: Remove silêncios dos arquivos MP3, otimizando o conteúdo de áudio.
- **Conversão opcional para MP4**: Transforma arquivos MP3 em vídeos MP4 com uma tela branca de fundo, se necessário.
- **Reconversão MP4 para MP3**: Após a edição, reconverte os vídeos MP4 de volta para o formato MP3.
- **Integração com MinIO**: Realiza upload automatizado dos arquivos processados e organiza-os em buckets MinIO.
- **Gerenciamento de arquivos temporários**: Remove automaticamente arquivos temporários para economizar espaço.

## Tecnologias utilizadas:

- **Python**: Linguagem principal utilizada no projeto.
- **MinIO SDK**: Para integração e gerenciamento de buckets.
- **MoviePy**: Biblioteca para manipulação de áudio e vídeo.
- **Auto-Editor**: Ferramenta para edição de arquivos com remoção de silêncios.
- **Subprocess**: Para executar comandos externos durante o processo.

## Como executar:

1. **Instale as dependências necessárias**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure as variáveis de ambiente do MinIO**:
   - `MINIO_URL`: URL do servidor MinIO.
   - `MINIO_PORT`: Porta do servidor MinIO.
   - `MINIO_ROOT_USER`: Usuário root do MinIO.
   - `MINIO_ROOT_PASSWORD`: Senha do usuário root do MinIO.

3. **Execute o script principal**:
   ```bash
   python main.py
   ```

## Estrutura do projeto:

- `main.py`: Script principal que executa o pipeline de processamento.
- `utils.py`: Funções auxiliares como log e notificações.
- `/opt/app/foredit/`: Diretório temporário para arquivos baixados e convertidos.
- `/opt/app/edited/`: Diretório para arquivos editados antes do upload.

## Contribuições:
Contribuições são bem-vindas! Por favor, abra uma issue ou envie um pull request para melhorias e correções.

## Licença:
Este projeto está licenciado sob a [MIT License](LICENSE).

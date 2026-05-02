import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ApiExceptionFilter } from './modules/platform/api-exception.filter';

async function bootstrap(): Promise<void> {
  const app = await NestFactory.create(AppModule);
  app.enableCors();
  app.useGlobalFilters(new ApiExceptionFilter());

  const port = Number(process.env.PORT ?? 3000);
  await app.listen(port);
}

void bootstrap();
